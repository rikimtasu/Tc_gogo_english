"""CRILAYLA compression and decompression for CRI CPK assets."""

import struct


def decompress(src: bytes) -> bytes:
    """Decompress a CRILAYLA-compressed payload."""
    if src[:8] != b"CRILAYLA":
        raise ValueError(f"Expected CRILAYLA magic, got {src[:8]!r}")
    uncomp_size, comp_size = struct.unpack_from("<II", src, 8)
    prefix = src[0x10 + comp_size : 0x10 + comp_size + 0x100]
    if len(prefix) != 0x100:
        raise ValueError("Truncated CRILAYLA 0x100-byte raw prefix")
    stream = src[0x10 : 0x10 + comp_size]

    bitbuf = 0
    bitcnt = 0
    ip = len(stream)

    def getbits(n: int) -> int:
        nonlocal bitbuf, bitcnt, ip
        while bitcnt < n:
            ip -= 1
            if ip < 0:
                raise EOFError("Unexpected end of CRILAYLA bitstream")
            bitbuf = (bitbuf << 8) | stream[ip]
            bitcnt += 8
        bitcnt -= n
        val = (bitbuf >> bitcnt) & ((1 << n) - 1)
        bitbuf &= (1 << bitcnt) - 1
        return val

    out = bytearray(uncomp_size)
    op = uncomp_size
    while op > 0:
        if getbits(1):
            off = getbits(13) + 3
            ln = getbits(2)
            if ln == 3:
                x = getbits(3)
                ln += x
                if x == 7:
                    x = getbits(5)
                    ln += x
                    if x == 31:
                        while True:
                            x = getbits(8)
                            ln += x
                            if x != 255:
                                break
            ln += 3
            for _ in range(ln):
                op -= 1
                out[op] = out[op + off]
        else:
            op -= 1
            out[op] = getbits(8)
    return bytes(prefix) + bytes(out)


def compress(data: bytes) -> bytes:
    """Compress raw bytes into CRILAYLA format using backward LZ77 matching."""
    if len(data) < 0x100:
        raise ValueError("CRILAYLA requires at least 0x100 bytes")
    prefix = data[:0x100]
    body = data[0x100:]
    n = len(body)

    tokens: list[tuple[int, int]] = []  # (bits, bitlen) pushed in reverse order
    bitbuf = 0
    bitcnt = 0
    out_bytes = bytearray()

    def putbits(val: int, nbits: int) -> None:
        nonlocal bitbuf, bitcnt
        # Since decompressor reads bytes from end of stream backwards and MSB-first,
        # we accumulate bits MSB-first into bytes from end of stream backwards (i.e. emit forward then reverse).
        bitbuf = (bitbuf << nbits) | (val & ((1 << nbits) - 1))
        bitcnt += nbits
        while bitcnt >= 8:
            bitcnt -= 8
            out_bytes.append((bitbuf >> bitcnt) & 0xFF)
            bitbuf &= (1 << bitcnt) - 1

    # Hash-chain match finder scanning backwards from n-1 down to 0
    # Matches look ahead (towards higher indices, already decoded in backward pass).
    head: dict[bytes, list[int]] = {}
    pos = n
    # Pre-seed nothing; add positions as pos moves down from n-1 to 0
    while pos > 0:
        best_len = 0
        best_off = 0
        if pos >= 3 and pos + 3 <= n:
            # Wait: at step emitting body[pos - best_len : pos], decompressor fills op = pos - 1 down to pos - best_len
            # reading out[op + off] where op + off <= n - 1 and 3 <= off <= 8194.
            pass
        # Simpler & exact: when decoding backwards, op steps down from pos-1.
        # On match of length L with offset off, it copies out[op + off] for op = pos-1 .. pos-L.
        # So body[pos - k] == body[pos - k + off] for k = 1..L, with pos - 1 + off < n => off <= n - pos.
        max_off = min(8194, n - pos)
        if pos >= 3 and max_off >= 3:
            key = body[pos - 3 : pos]
            cand = head.get(key)
            if cand:
                limit = pos + max_off - 3
                for mpos in reversed(cand):
                    off = (mpos + 3) - pos
                    if off < 3:
                        continue
                    if off > max_off:
                        break
                    # Check match extending backwards from pos-1 down to 0
                    l = 3
                    max_l = pos
                    while l < max_l and body[pos - 1 - l] == body[pos - 1 - l + off]:
                        l += 1
                    if l > best_len:
                        best_len = l
                        best_off = off
                        if best_len >= 256:
                            break
        if best_len >= 3:
            putbits(1, 1)
            putbits(best_off - 3, 13)
            rem = best_len - 3
            if rem < 3:
                putbits(rem, 2)
            else:
                putbits(3, 2)
                rem -= 3
                if rem < 7:
                    putbits(rem, 3)
                else:
                    putbits(7, 3)
                    rem -= 7
                    if rem < 31:
                        putbits(rem, 5)
                    else:
                        putbits(31, 5)
                        rem -= 31
                        while rem >= 255:
                            putbits(255, 8)
                            rem -= 255
                        putbits(rem, 8)
            for k in range(best_len):
                p = pos - 1 - k
                if p >= 2 and p + 1 <= n:
                    hkey = body[p - 2 : p + 1]
                    lst = head.setdefault(hkey, [])
                    lst.append(p - 2)
                    if len(lst) > 32:
                        del lst[0]
            pos -= best_len
        else:
            pos -= 1
            putbits(0, 1)
            putbits(body[pos], 8)
            if pos >= 2 and pos + 1 <= n:
                hkey = body[pos - 2 : pos + 1]
                lst = head.setdefault(hkey, [])
                lst.append(pos - 2)
                if len(lst) > 32:
                    del lst[0]

    if bitcnt > 0:
        out_bytes.append((bitbuf << (8 - bitcnt)) & 0xFF)
    stream = bytes(reversed(out_bytes))
    header = b"CRILAYLA" + struct.pack("<II", n, len(stream))
    return header + stream + prefix
