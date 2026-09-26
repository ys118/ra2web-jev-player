# -*- coding: utf-8 -*-
"""decode_csf.py —— 从游戏客户端 ra2.csf 解出中文名表（label -> 文本）。

CSF 格式要点（RA2/共辉网页版实测）：
  - 头: b" FSC" + int32 version + int32 numLabels + int32 numStrings (+ version>=3 时 4 字节保留)
  - 每条: b" LBL" + int32 值个数(实测=1) + int32 len + label 字节
          b" RTS" + int32 len(UTF-16 码元数) + 值字节
  - **值里每个 UTF-16LE 码元按位取反 (XOR 0xFFFF)** —— 这是最关键的坑
    （例: b"\\xff\\xa0" -> 0xA0FF ^ 0xFFFF = 0x5F00 = "开"）
  - 本 mod 的文件里 LBL 后多一个 int32（值个数），解析时按启发式兼容两种布局

用法:
  python decode_csf.py                      # ra2.csf -> csf_decoded.json（同目录）
  python decode_csf.py --compare            # 解码后与现有 csf_decoded.json 对比校验
  python decode_csf.py in.csf out.json
"""
import io
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LBL = b" LBL"
RTS = b" RTS"


def decode_value(buf: bytes) -> str:
    """UTF-16LE 码元逐一 XOR 0xFFFF，再滤掉控制字符。"""
    chars = []
    for i in range(0, len(buf) - 1, 2):
        w = buf[i] | (buf[i + 1] << 8)
        c = w ^ 0xFFFF
        if c == 0:
            continue
        if c < 0x20 and c not in (0x09, 0x0A, 0x0D):
            continue
        chars.append(chr(c))
    return "".join(chars)


def parse_csf(path: str) -> dict:
    raw = io.open(path, "rb").read()
    if raw[:4] != b" FSC":
        raise ValueError("不是 CSF 文件（签名不符）: %r" % raw[:4])
    version, n_labels, n_strings = struct.unpack_from("<iii", raw, 4)
    pos = raw.find(b" LBL", 16)          # 头部长度随版本变化（本文件 24），直接定位首条记录
    if pos < 0:
        raise ValueError("找不到任何 LBL 记录")

    def is_tag(b, name):
        # 记录 tag 的第 1 字节是标志位（' ' 常规 / 'W' 带 ASCII 附加串），后 3 字节才是名字
        return b[1:4] == name

    out = {}
    while pos + 8 <= len(raw) and len(out) < n_labels:
        # ---- 标签 ----
        if not is_tag(raw[pos:pos + 4], b"LBL"):
            nxt = raw.find(b" LBL", pos)
            if nxt < 0:
                break
            pos = nxt
            continue
        d1, d2 = struct.unpack_from("<ii", raw, pos + 4)
        if 0 < d2 < 512 and raw[pos + 12:pos + 16].isascii():
            n_vals, llen, off = d1, d2, pos + 12      # LBL + 值个数 + 长度 + 标签
        else:
            n_vals, llen, off = 1, d1, pos + 8        # LBL + 长度 + 标签
        if not (0 < llen < 512):
            pos += 4
            continue
        label = raw[off:off + llen].decode("latin-1")
        pos = off + llen
        # ---- 值（可能多组） ----
        for _ in range(max(1, n_vals)):
            if pos + 8 > len(raw) or not is_tag(raw[pos:pos + 4], b"RTS"):
                break
            flag = raw[pos]
            (vlen,) = struct.unpack_from("<i", raw, pos + 4)
            pos += 8
            if vlen < 0 or pos + vlen * 2 > len(raw):
                pos = len(raw)
                break
            out[label] = decode_value(raw[pos:pos + vlen * 2])
            pos += vlen * 2
            # 'W' 标记：值后跟 (int32 字节长度 + ASCII 附加串)，如 VOX:CEVA001 -> "ceva001"
            if flag == 0x57 and pos + 4 <= len(raw):
                (elen,) = struct.unpack_from("<i", raw, pos)
                if 0 <= elen <= 4096:
                    pos += 4 + elen
            elif pos + 8 <= len(raw) and not is_tag(raw[pos:pos + 4], b"LBL") \
                    and not is_tag(raw[pos:pos + 4], b"RTS"):
                (elen,) = struct.unpack_from("<i", raw, pos)
                if 0 <= elen <= 4096:
                    pos += 4 + elen
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    compare = "--compare" in sys.argv
    src = args[0] if args else os.path.join(HERE, "ra2.csf")
    dst = args[1] if len(args) > 1 else os.path.join(HERE, "csf_decoded.json")

    data = parse_csf(src)
    io.open(dst, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=1))
    print("解码 %d 条 -> %s" % (len(data), dst))

    if compare and os.path.exists(dst):
        old = json.load(io.open(dst, encoding="utf-8"))
        same = sum(1 for k, v in data.items() if old.get(k) == v)
        diff = [(k, old.get(k), data.get(k)) for k in list(data)[:2000] if k in old and old[k] != v]
        print("对比现有文件: 共同键 %d, 完全一致 %d, 不一致 %d" % (
            len(set(data) & set(old)), same, len(diff)))
        for k, a, b in diff[:10]:
            print("  差异", k, "| 旧:", repr(a)[:40], "| 新:", repr(b)[:40])
    for probe in ("NAME:HTNK", "NAME:NAREFN", "NAME:E2", "NAME:HARV"):
        print("  样例", probe, "=", data.get(probe))


if __name__ == "__main__":
    main()
