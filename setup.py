"""Builds the macOS app: see the README, section "Rebuilding the .app"."""

from setuptools import setup

setup(
    app=["app.py"],
    name="Peter Lynch Fair Value",
    options={
        "py2app": {
            "iconfile": "AppIcon.icns",
            "includes": ["lynch", "storage"],
            # The app does not use the network: leave out SSL/OpenSSL and the network
            # modules, so we don't ship code (and vulnerabilities) we don't need.
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
