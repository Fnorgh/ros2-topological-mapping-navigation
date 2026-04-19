#!/usr/bin/env python3
"""Generate test QR code images: test_qr1.png, test_qr2.png, test_qr3.png"""
import sys

try:
    import qrcode
except ImportError:
    print("Installing qrcode...")
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'qrcode[pil]'])
    import qrcode

CODES = ['test1', 'test2', 'test3']

for content in CODES:
    img = qrcode.make(content)
    filename = f'test_qr_{content}.png'
    img.save(filename)
    print(f'Saved {filename}  (data: "{content}")')

print('\nDone. Show these images to the robot camera to trigger QR detection.')
