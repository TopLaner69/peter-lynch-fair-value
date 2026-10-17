"""Construiește aplicația macOS: vezi README, secțiunea „Reconstruire .app”."""

from setuptools import setup

setup(
    app=["app.py"],
    name="Peter Lynch Fair Value",
    options={
        "py2app": {
            "iconfile": "AppIcon.icns",
            "includes": ["lynch", "storage"],
            # Aplicația nu folosește rețeaua: scoatem SSL/OpenSSL și modulele de rețea,
            # ca să nu includem cod (și vulnerabilități) de care nu avem nevoie.
            "excludes": ["setuptools", "distutils", "pkg_resources", "unittest",
                         "ssl", "_ssl", "_hashlib", "http", "urllib.request", "ftplib",
                         "smtplib", "imaplib", "poplib", "xmlrpc", "asyncio",
                         "socketserver", "webbrowser"],
            "plist": {
                "CFBundleName": "Peter Lynch Fair Value",
                "CFBundleDisplayName": "Peter Lynch Fair Value",
                "CFBundleIdentifier": "local.peterlynch.fairvalue",
                "CFBundleShortVersionString": "1.0",
                "NSHighResolutionCapable": True,
            },
        }
    },
)
