#!/usr/bin/env python
# -*- coding=utf-8 -*-


'''
A WSGI application entry.
'''

import sys
sys.path.append('transwarp')
import logging; logging.basicConfig(level=logging.INFO)

import os

import db
from web import WSGIApplication, Jinja2TemplateEngine

from config import configs

# init db:
db.create_engine(**configs.db)

# init wsgi app:
wsgi = WSGIApplication(os.path.dirname(os.path.abspath(__file__)))

template_engine = Jinja2TemplateEngine(os.path.join(os.path.abspath(__file__), 'templates'))

wsgi.template_engine = template_engine

import urls

wsgi.add_module(urls)

if __name__ == '__main__':
    wsgi.run(9000)

