"""Original looping Commons score. Standard MIDI file, no samples or dependencies."""
from pathlib import Path
import struct


def variable(value):
    output = [value & 127]
    while value >> 7:
        value >>= 7
        output.insert(0, (value & 127) | 128)
    return bytes(output)


def track(events):
    previous = 0
    output = bytearray()
    for tick, data in sorted(events, key=lambda item: item[0]):
        output.extend(variable(tick - previous)); output.extend(data); previous = tick
    output.extend(b'\x00\xff\x2f\x00')
    return b'MTrk' + struct.pack('>I', len(output)) + output


def compose():
    division, bars = 480, 16
    tempo = 681818  # 88 BPM; display timing never enters world history.
    conductor = [(0, b'\xff\x51\x03' + tempo.to_bytes(3, 'big')),
                 (0, b'\xff\x03\x12Commons / becoming'), (bars*4*division, b'\xff\x01\x00')]
    channels = [[(0, bytes([0xc0+i, program]))] for i,program in enumerate([89,10,38])]
    roots = [48,53,51,46]
    def note(channel,tick,pitch,length,velocity):
        channels[channel].append((tick,bytes([0x90+channel,pitch,velocity])))
        channels[channel].append((tick+length,bytes([0x80+channel,pitch,0])))
    for bar in range(bars):
        root = roots[(bar//2)%len(roots)]
        start = bar*4*division
        for offset in (0,7,14,19):
            note(0,start,root+offset,division*4-20,33+(bar%3)*3)
        pattern=[0,7,14,19,14,7,22,14]
        for step,offset in enumerate(pattern):
            note(1,start+step*division//2,root+12+offset,division//3,46+((step*7+bar*3)%18))
        note(2,start,root-12,division*3,48)
        if bar%2:
            note(2,start+division*3,root-5,division-20,38)
    return b'MThd'+struct.pack('>IHHH',6,1,4,division)+track(conductor)+b''.join(track(events) for events in channels)


if __name__ == '__main__':
    target=Path(__file__).resolve().parents[1]/'commons_game/web/commons.mid'
    target.write_bytes(compose())
    print(f'Original MIDI score: {target} ({target.stat().st_size} bytes)')
