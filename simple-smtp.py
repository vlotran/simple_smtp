import asyncio
from datetime import datetime
from pathlib import Path

SAVE_DIR = Path("emails")
SAVE_DIR.mkdir(exist_ok=True)

class SMTPSession:
    def __init__(self):
        self.mail_from = None
        self.rcpt_to = []
        self.data_lines = []

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    peer = writer.get_extra_info("peername")
    s = SMTPSession()

    def log(msg: str):
        print(f"[{peer}] {msg}", flush=True)

    async def send(line: str):
        writer.write((line + "\r\n").encode("utf-8"))
        await writer.drain()

    await send("220 smtp-lab.local Simple SMTP capture server ready")
    log("Connected")

    in_data = False

    while True:
        raw = await reader.readline()
        if not raw:
            log("Disconnected")
            break

        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        log(f"C: {line}")

        if in_data:
            if line == ".":
                in_data = False

                ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")
                fname = SAVE_DIR / f"email-{ts}.eml"
                content = "\r\n".join(s.data_lines) + "\r\n"

                fname.write_text(
                    "X-Received-By: simple-smtp.py\r\n"
                    f"X-Mail-From: {s.mail_from}\r\n"
                    f"X-Rcpt-To: {', '.join(s.rcpt_to)}\r\n"
                    + content,
                    encoding="utf-8",
                    errors="replace",
                )

                log(f"Saved to {fname}")
                await send(f"250 OK : queued as {fname.name}")

                s = SMTPSession()
            else:
                if line.startswith(".."):  # dot-stuffing
                    line = line[1:]
                s.data_lines.append(line)
            continue

        upper = line.upper()

        if upper.startswith("EHLO") or upper.startswith("HELO"):
            await send("250-smtp-lab.local")
            await send("250 SIZE 10485760")
        elif upper.startswith("MAIL FROM:"):
            s.mail_from = line[10:].strip()
            await send("250 OK")
        elif upper.startswith("RCPT TO:"):
            s.rcpt_to.append(line[8:].strip())
            await send("250 OK")
        elif upper == "DATA":
            if not s.mail_from or not s.rcpt_to:
                await send("503 Bad sequence of commands")
            else:
                await send("354 End data with <CR><LF>.<CR><LF>")
                in_data = True
        elif upper == "RSET":
            s = SMTPSession()
            await send("250 OK")
        elif upper == "NOOP":
            await send("250 OK")
        elif upper == "QUIT":
            await send("221 Bye")
            break
        else:
            await send("250 OK")

    writer.close()
    await writer.wait_closed()

async def main(host="0.0.0.0", port=2525):
    server = await asyncio.start_server(handle_client, host, port)
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    print(f"Listening on {addrs}", flush=True)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
PY