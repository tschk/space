"""Shared read-only framebuffer oracle for actual readable native GUI tests."""
from pathlib import Path
import hashlib
import re
import json
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


def image_canvas_kind(path):
    blob = Path(path).read_bytes()
    table = struct.unpack_from('<Q', blob, 0xf00)[0] - 0x100000
    magic, count = struct.unpack_from('<QQ', blob, table)
    assert magic == 0x5350414345424f4f
    for index in range(count):
        kind, physical, size, reserved = struct.unpack_from('<QQQQ', blob, table + 16 + index * 32)
        assert reserved == 0
        if kind in (20, 23):
            trailer = 64
            if kind == 23: trailer = 128
            offset = physical - 0x100000 + size - trailer
            return kind if size >= trailer + 64 and struct.unpack_from('<Q', blob, offset)[0] == 0x5350414345434e56 else 0
    return 0


def image_has_canvas(path):
    return image_canvas_kind(path)!=0


def image_has_protected_canvas(path):
    return image_canvas_kind(path)==23


class WindowEvidence:
    def __init__(self, root, protected=False):
        self.protected=protected
        self.mature={}
        if protected:
            from PIL import ImageFont
            self.fonts={}
            pins={'DejaVuSansMono.ttf':'54bf827eb99404e8f430c330ad30f063334f637eba0109b6a18d4f566a8e9dd8',
                  'DejaVuSans.ttf':'57f73e11f51999432bf7ab22ce55b6f945d5eca1bf824404cfa9ec2e3718c84e'}
            for face,name in enumerate(pins):
                path=Path(root)/'assets/fonts/desktop'/name
                assert hashlib.sha256(path.read_bytes()).hexdigest()==pins[name]
                for scale in (2,3):self.fonts[scale,face]=ImageFont.truetype(str(path),14 if scale==2 else 21)
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

    def mature_glyph(self,face,scale,code):
        """Independent mature raster/advance oracle, never native atlas input."""
        key=(face,scale,code)
        if key not in self.mature:
            from PIL import Image,ImageDraw
            extent=8*scale;baseline=13*scale//2;limit=extent
            font=self.fonts[scale,face];tile=Image.new('L',(extent,extent))
            ImageDraw.Draw(tile).text((0,baseline),chr(code),font=font,fill=255,anchor='ls')
            advance=5*scale if face==0 else max(1,int(font.getlength(chr(code))+.5))
            if face==1:limit=advance
            box=tile.getbbox()
            if box and box[2]>limit:
                ink=tile.crop((0,0,box[2],extent)).resize((limit,extent),Image.Resampling.LANCZOS)
                tile=Image.new('L',(extent,extent));tile.paste(ink,(0,0))
            self.mature[key]=(tile.tobytes(),advance)
        return self.mature[key]

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

    def capture(self, monitor, path, layout, timeout_seconds=5):
        path = Path(path)
        path.unlink(missing_ok=True)
        monitor.sendall(f'screendump {path}\n'.encode())
        expected = layout['output_width'] * layout['output_height'] * 3
        deadline = time.monotonic() + timeout_seconds
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

    def capture_checked(self, monitor, path, layout, texts, focused, timeout_seconds=5):
        """Wait for the full unchanged oracle, with a finite evidence receipt.

        This synchronizes a test with an in-progress scanout repaint. It does
        not establish atomic presentation or change any expected pixel.
        """
        path = Path(path)
        started = time.monotonic()
        deadline = started + timeout_seconds
        self.capture_sequence = getattr(self, 'capture_sequence', 0) + 1
        receipt = {'synchronization_only': True, 'atomic_presentation_proof': False,
                   'capture_sequence': self.capture_sequence, 'path': path.name,
                   'layout': layout, 'expected_texts': texts, 'focused': focused,
                   'attempts': 0, 'timeout_seconds': timeout_seconds, 'errors': []}
        last_error = None
        while time.monotonic() < deadline:
            receipt['attempts'] += 1
            try:
                rgb = self.capture(monitor, path, layout, deadline - time.monotonic())
                self.check(rgb, layout, texts, focused)
                receipt['status'] = 'passed'
                receipt['elapsed_seconds'] = time.monotonic() - started
                self.record_capture(path, receipt)
                return rgb
            except AssertionError as error:
                last_error = error
                receipt['errors'].append({'attempt': receipt['attempts'], 'error': repr(error)})
                if path.exists():
                    frame = path.read_bytes()
                    if receipt['attempts'] == 1:
                        path.with_suffix('.failed-first.ppm').write_bytes(frame)
                        first = path.with_name(path.stem + f'.capture-{self.capture_sequence}.failed-first.ppm')
                        first.write_bytes(frame)
                        receipt['first_failed_frame'] = first.name
                    path.with_suffix('.failed-last.ppm').write_bytes(frame)
                    last = path.with_name(path.stem + f'.capture-{self.capture_sequence}.failed-last.ppm')
                    last.write_bytes(frame)
                    receipt['last_failed_frame'] = last.name
                remaining = deadline - time.monotonic()
                if remaining > 0: time.sleep(min(.05, remaining))
        receipt['status'] = 'failed'
        receipt['elapsed_seconds'] = time.monotonic() - started
        self.record_capture(path, receipt)
        raise AssertionError(f'complete framebuffer oracle timed out after {receipt["attempts"]} attempts: {last_error!r}') from last_error

    def record_capture(self, path, receipt):
        path.with_suffix('.capture.json').write_text(json.dumps(receipt, indent=2) + '\n')
        with (path.parent / 'capture-history.jsonl').open('a') as log:
            log.write(json.dumps(receipt) + '\n')

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
                if self.protected:
                    coverage,advance=self.mature_glyph(face,s,code)
                    extent=8*s;columns=advance if index<len(value)-1 else extent
                    for row in range(extent):
                        for column in range(columns):
                            alpha=coverage[row*extent+column] if column<extent else 0
                            expected=bytes((f*alpha+b*(255-alpha))//255 for f,b in zip(foreground,background))
                            if caret is not None and caret<=cursor+column<caret+s:expected=ACTIVE
                            pixel(cursor+column,y+row,expected,('mature glyph',face,value,index))
                    cursor+=advance
                    continue
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
            cursor = content[2] if len(content) == 3 else len(content[0])
            assert 0 <= cursor <= len(content[0])
            cell=5 if self.protected else 8
            caret = left + (8 + cursor * cell) * s if focused == slot else None
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
