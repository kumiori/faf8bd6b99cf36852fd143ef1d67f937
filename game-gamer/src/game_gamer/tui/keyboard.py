"""Small keyboard boundary: line scripts and POSIX arrow/Esc navigation."""
import os
import select


def navigation(source, output):
    if not getattr(source,'isatty',lambda:False)() or not getattr(output,'isatty',lambda:False)():
        line = source.readline()
        if not line:
            raise EOFError
        return decode(line.rstrip('\r\n'))
    try:
        import termios
        import tty
        fd = source.fileno()
    except (ImportError,AttributeError,OSError):
        line = source.readline()
        if not line:
            raise EOFError
        return decode(line.rstrip('\r\n'))
    original = termios.tcgetattr(fd); typed = bytearray()
    try:
        tty.setcbreak(fd)
        while True:
            char = os.read(fd,1)
            if char in {b'\r',b'\n'}:
                output.write('\n');output.flush()
                return typed.decode('utf-8','replace')
            if char == b'\x03':
                raise KeyboardInterrupt
            if not char or char==b'\x04':
                raise EOFError
            if char == b'\x1b':
                escape = char
                while select.select([fd],[],[],.04)[0]:
                    escape += os.read(fd,1)
                    if len(escape)>=3:
                        break
                return decode(escape.decode('ascii','ignore'))
            if char in {b'\x7f',b'\x08'}:
                if typed:
                    typed.pop(); output.write('\b \b');output.flush()
            else:
                typed.extend(char)
                # UTF-8 input is displayed as complete characters.
                try:
                    text = typed.decode('utf-8')
                    if text:
                        output.write('\r> '+text);output.flush()
                except UnicodeDecodeError:
                    pass
    finally:
        termios.tcsetattr(fd,termios.TCSADRAIN,original)


def decode(value):
    return {'\x1b[A':'up','\x1b[B':'down','\x1b[C':'next','\x1b[D':'prev','\x1b':'b',
            '\t':'tab','\x1b[Z':'backtab'}.get(value,value.strip())
