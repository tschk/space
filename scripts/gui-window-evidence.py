"""Shared read-only framebuffer oracle for actual readable native GUI tests."""
from pathlib import Path
import re
import struct
import time

BACKGROUND = bytes((17, 22, 31))
WINDOW = bytes((28, 36, 48))
TITLE = bytes((38, 50, 70))
FIELD = bytes((17, 23, 33))
WHITE = bytes((243, 245, 248))
LABEL = bytes((181, 194, 214))
GREEN = bytes((138, 214, 174))
ACTIVE = bytes((136, 181, 255))
INACTIVE = bytes((77, 86, 102))


def image_has_canvas(path):
    blob = Path(path).read_bytes()
    table = struct.unpack_from('<Q', blob, 0xf00)[0] - 0x100000
    magic, count = struct.unpack_from('<QQ', blob, table)
    assert magic == 0x5350414345424f4f
    for index in range(count):
        kind, physical, size, reserved = struct.unpack_from('<QQQQ', blob, table + 16 + index * 32)
        assert reserved == 0
        if kind == 20:
            offset = physical - 0x100000 + size - 64
            return size >= 128 and struct.unpack_from('<Q', blob, offset)[0] == 0x5350414345434e56
    return False


class WindowEvidence:
    def __init__(self, root):
        source = (Path(root) / 'components/font.in').read_text()
        self.faces = [{}, {}]
        self.advance = {}
        for match in re.finditer(r'fb-font(-sans)?-set\(([^)]+)\)', source):
            try:
                values = [int(v.strip(), 0) for v in match.group(2).split(',')]
            except ValueError:
                continue
            face = int(bool(match.group(1)))
            if len(values) == 9 + face:
                self.faces[face][values[0]] = values[1 + face:]
                if face:
                    self.advance[values[0]] = values[1]
        assert self.faces[0] and self.faces[1]

    def layout(self, serial):
        matches = re.findall(rb'gui-window: mode (\d+)x(\d+) pitch (\d+) extent (\d+)x(\d+) scale (\d+) generation (\d+) slots (\d+) (\d+) (\d+)\r?\n', bytes(serial))
        assert matches, 'no actual product layout receipt'
        names = ('output_width', 'output_height', 'pitch', 'width', 'height', 'scale', 'generation', 'left', 'right', 'top')
        result = dict(zip(names, map(int, matches[-1])))
        s = result['scale']
        assert s in (2, 3)
        assert 128 * s <= result['width'] <= 768 and 64 * s <= result['height'] <= 384
        assert result['width'] % s == result['height'] % s == 0
        assert result['pitch'] >= result['output_width'] * 4 and result['pitch'] % 4 == 0
        assert 0 <= result['left'] < result['left'] + result['width'] < result['right']
        assert result['right'] + result['width'] <= result['output_width']
        assert 0 <= result['top'] and result['top'] + result['height'] <= result['output_height']
        return result

    def capture(self, monitor, path, layout):
        path = Path(path)
        path.unlink(missing_ok=True)
        monitor.sendall(f'screendump {path}\n'.encode())
        expected = layout['output_width'] * layout['output_height'] * 3
        deadline = time.monotonic() + 5
        frame = []
        while len(frame) != 4 or len(frame[3]) != expected:
            assert time.monotonic() < deadline, 'readable GUI screendump timeout'
            if path.exists():
                frame = path.read_bytes().split(b'\n', 3)
                if len(frame) == 4 and len(frame[3]) == expected:
                    break
            time.sleep(.02)
        assert frame[:3] == [b'P6', f"{layout['output_width']} {layout['output_height']}".encode(), b'255']
        assert len(frame[3]) == layout['output_width'] * layout['output_height'] * 3
        return frame[3]

    def check(self, rgb, layout, texts, focused):
        s, width, height, top = (layout[n] for n in ('scale', 'width', 'height', 'top'))
        output_width = layout['output_width']

        def pixel(x, y, expected, label):
            offset = (y * output_width + x) * 3
            actual = rgb[offset:offset + 3]
            assert actual == expected, (label, x, y, actual, expected, layout)

        def text(face, x, y, value, foreground, background, cells=None, caret=None):
            cursor = x
            value = value.ljust(cells) if cells is not None else value
            for index, ch in enumerate(value):
                code = ord(ch)
                bits = self.faces[face].get(code, [0] * 8)
                advance = 8 if face == 0 else self.advance[code]
                # A proportional glyph's painted box can overlap its next cell;
                # compare its advance, including the final full glyph box.
                columns = advance if index < len(value) - 1 else 8
                for row in range(8 * s):
                    for column in range(columns * s):
                        expected = foreground if bits[row // s] & (128 >> (column // s)) else background
                        if caret is not None and cursor + column == caret and row < 8 * s:
                            expected = ACTIVE
                        elif caret is not None and caret <= cursor + column < caret + s:
                            expected = ACTIVE
                        pixel(cursor + column, y + row, expected, ('glyph', face, value, index))
                cursor += advance * s

        for slot, content in enumerate(texts):
            left = layout['left' if slot == 0 else 'right']
            if content is None:
                for y in range(top, top + height):
                    for x in range(left, left + width):
                        pixel(x, y, BACKGROUND, 'closed surface')
                continue
            border = ACTIVE if focused == slot else INACTIVE
            for x in range(left, left + width):
                pixel(x, top, border, 'window top border')
                pixel(x, top + height - 1, border, 'window bottom border')
            for y in range(top, top + height):
                pixel(left, y, border, 'window left border')
                pixel(left + width - 1, y, border, 'window right border')
            text(1, left + 8 * s, top + 4 * s, 'Calculator' if slot == 0 else 'Notes', WHITE, TITLE)
            text(1, left + 8 * s, top + 24 * s, 'Expression' if slot == 0 else 'Text (8 chars)', LABEL, WINDOW)
            caret = left + (8 + len(content[0]) * 8) * s if focused == slot else None
            text(0, left + 8 * s, top + 37 * s, content[0], WHITE, FIELD, cells=9, caret=caret)
            text(1, left + 8 * s, top + 58 * s, 'Result' if slot == 0 else 'File /gui-note.txt', LABEL, WINDOW)
            text(0, left + 8 * s, top + 74 * s, content[1], WHITE if slot == 0 else GREEN, WINDOW, cells=8)
            text(1, left + 8 * s, top + 94 * s, 'Enter to calculate' if slot == 0 else 'Ctrl+S save', LABEL, WINDOW)
            text(1, left + 8 * s, top + 106 * s, 'Tab focus | Esc close', LABEL, WINDOW)
            text(1, left + 8 * s, top + 118 * s, 'Ctrl+G size | Ctrl+O mode', LABEL, WINDOW)

    def pointer_target(self, layout, slot):
        assert slot in (0, 1)
        left = layout['left' if slot == 0 else 'right']
        return left + layout['width'] // 2, layout['top'] + layout['height'] // 2

    def focus_pointer(self, monitor, wait, serial, slot):
        layout = self.layout(serial)
        left = layout['left' if slot == 0 else 'right']
        target = (left + layout['width'] // 2, layout['top'] + 8 * layout['scale'])

        def move(x, y):
            for _ in range(max(layout['output_width'], layout['output_height']) // 100 + 3):
                monitor.sendall(b'mouse_move -100 -100\n'); time.sleep(.02)
            while x or y:
                dx, dy = min(x, 100), min(y, 100)
                monitor.sendall(f'mouse_move {dx} {dy}\n'.encode())
                x -= dx; y -= dy; time.sleep(.03)
            time.sleep(.1)

        move(*target)
        start = len(serial)
        monitor.sendall(b'mouse_button 1\n')
        wait(b'gui: pointer focused app ', start)
        monitor.sendall(b'mouse_button 0\n')
        move(10, layout['output_height'] - 20)
        return {'slot': slot, 'x': target[0], 'y': target[1], 'layout': layout}
