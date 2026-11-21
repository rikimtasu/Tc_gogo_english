"""Read-only CRI CPK TOC lister (unencrypted @UTF only)."""
import struct, sys, collections

def read_utf(buf):
    assert buf[:4] == b"@UTF", buf[:4]
    tsize, rows_off, str_off, data_off, name_off, ncols, row_len, nrows = struct.unpack(">IIIIIHHI", buf[4:32])
    base = 8
    strs = buf[base + str_off: base + data_off]
    def s(o):
        e = strs.index(b"\0", o); return strs[o:e].decode("cp932", "replace")
    cols = []; p = 32
    for _ in range(ncols):
        flags = buf[p]; nm = struct.unpack(">I", buf[p+1:p+5])[0]; p += 5
        storage, typ = flags & 0xF0, flags & 0x0F
        const = None
        if storage == 0x30:
            const, p = val(buf, p, typ, s, base, data_off)
        cols.append((s(nm), storage, typ, const))
    rows = []
    for r in range(nrows):
        q = base + rows_off + r * row_len; row = {}
        for nm, storage, typ, const in cols:
            if storage == 0x50:
                row[nm], q = val(buf, q, typ, s, base, data_off)
            else:
                row[nm] = const
        rows.append(row)
    return s(name_off), rows

def val(buf, p, typ, s, base, data_off):
    fmt = {0:">B",1:">b",2:">H",3:">h",4:">I",5:">i",6:">Q",7:">q",8:">f"}
    if typ in fmt:
        n = struct.calcsize(fmt[typ]); return struct.unpack(fmt[typ], buf[p:p+n])[0], p + n
    if typ == 0xA:
        return s(struct.unpack(">I", buf[p:p+4])[0]), p + 4
    if typ == 0xB:
        o, l = struct.unpack(">II", buf[p:p+8]); return ("data", base + data_off + o, l), p + 8
    raise ValueError(typ)

def main(path):
    f = open(path, "rb"); hdr = f.read(0x800)
    _, rows = read_utf(hdr[0x10:])
    h = rows[0]
    print("header:", {k: v for k, v in h.items() if k in ("TocOffset","EtocOffset","ItocOffset","ContentOffset","Files","Align","Version")})
    toc_off = h.get("TocOffset")
    if not toc_off:
        print("no TOC (ID-only CPK)"); return
    f.seek(toc_off); t = f.read(16); size = struct.unpack("<Q", t[8:16])[0]
    body = f.read(size)
    _, files = read_utf(body)
    exts = collections.Counter(); dirs = collections.Counter()
    for r in files:
        n = r.get("FileName") or ""; exts[n.rsplit(".",1)[-1].lower() if "." in n else ""] += 1
        dirs[r.get("DirName") or ""] += 1
    print("files:", len(files)); print("dirs:", dirs.most_common(30)); print("exts:", exts.most_common(30))
    for r in files[:int(sys.argv[2]) if len(sys.argv) > 2 else 40]:
        print(r.get("DirName"), r.get("FileName"), r.get("FileSize"), r.get("ExtractSize"))

main(sys.argv[1])
