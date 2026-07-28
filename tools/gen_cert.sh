#!/bin/bash
# توليد شهادة SSL ذاتية التوقيع للتجارب
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
echo "[+] تم إنشاء cert.pem و key.pem"