#!/bin/bash
# Z3R0 Ghost Proxy - مثبت تلقائي لـ Kali / Termux
set -e

echo "[*] تثبيت الأدوات المطلوبة..."

if [ -d "/data/data/com.termux" ]; then
    pkg update -y && pkg upgrade -y
    pkg install python openssl-tool git -y
else
    sudo apt update && sudo apt install python3 python3-pip openssl git -y
fi

pip install --upgrade pip
pip install -r requirements.txt

echo "[+] تم التثبيت. استخدم ./run.sh للتشغيل السريع."