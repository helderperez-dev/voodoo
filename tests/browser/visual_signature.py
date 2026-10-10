"""Small dependency-free perceptual signatures for PNG browser captures."""

from __future__ import annotations

import struct
import zlib


def _png_pixels(data: bytes) -> tuple[int, int, bytes]:  # noqa: C901
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("visual capture is not a PNG")
    offset = 8
    width = height = color_type = bit_depth = None
    compressed = bytearray()
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        offset += length + 12
        if kind == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(
                ">IIBBBBB", chunk
            )
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            break
    if bit_depth != 8 or color_type not in {2, 6}:
        raise ValueError("visual capture must use an 8-bit RGB/RGBA PNG")
    raw = zlib.decompress(compressed)
    source_channels = 4 if color_type == 6 else 3
    stride = width * source_channels
    rows: list[bytes] = []
    previous = bytearray(stride)
    cursor = 0
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        scan = bytearray(raw[cursor : cursor + stride])
        cursor += stride
        for index in range(stride):
            left = scan[index - source_channels] if index >= source_channels else 0
            above = previous[index]
            upper_left = (
                previous[index - source_channels] if index >= source_channels else 0
            )
            if filter_type == 1:
                scan[index] = (scan[index] + left) & 255
            elif filter_type == 2:
                scan[index] = (scan[index] + above) & 255
            elif filter_type == 3:
                scan[index] = (scan[index] + ((left + above) // 2)) & 255
            elif filter_type == 4:
                estimate = left + above - upper_left
                distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
                predictor = (left, above, upper_left)[distances.index(min(distances))]
                scan[index] = (scan[index] + predictor) & 255
            elif filter_type != 0:
                raise ValueError(f"unsupported PNG filter: {filter_type}")
        if source_channels == 3:
            expanded = bytearray()
            for index in range(0, len(scan), 3):
                expanded.extend(scan[index : index + 3])
                expanded.append(255)
            rows.append(bytes(expanded))
        else:
            rows.append(bytes(scan))
        previous = scan
    return width, height, b"".join(rows)


def signature(data: bytes, size: int = 4) -> dict[str, object]:
    """Return dimensions and a quantized average RGBA thumbnail signature."""
    width, height, pixels = _png_pixels(data)
    values: list[int] = []
    for y in range(size):
        y0, y1 = y * height // size, (y + 1) * height // size
        for x in range(size):
            x0, x1 = x * width // size, (x + 1) * width // size
            total = [0, 0, 0, 0]
            count = 0
            for row in range(y0, max(y1, y0 + 1)):
                for col in range(x0, max(x1, x0 + 1)):
                    start = row * width * 4 + col * 4
                    for channel in range(4):
                        total[channel] += pixels[start + channel]
                    count += 1
            values.extend(channel_total // count // 16 for channel_total in total)
    return {"width": width, "height": height, "size": size, "pixels": values}


def distance(left: dict[str, object], right: dict[str, object]) -> float:
    """Return the fraction of thumbnail channels differing by more than one bin."""
    left_width = int(left["width"])
    right_width = int(right["width"])
    if left["size"] != right["size"] or abs(left_width - right_width) / max(right_width, 1) > 0.1:
        return 1.0
    left_height = int(left["height"])
    right_height = int(right["height"])
    if abs(left_height - right_height) / max(right_height, 1) > 0.1:
        return 1.0
    values = zip(left["pixels"], right["pixels"], strict=True)
    differing = sum(abs(int(a) - int(b)) > 1 for a, b in values)
    return differing / max(len(left["pixels"]), 1)
