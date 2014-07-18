#! /usr/bin/env python
# -*- utf-8 -*-

import sys
sys.path.append('transwarp')
from models import User, Blog, Comment

import db

db.create_engine('root', 'admin', 'awesome')

u = User(name='test',admin='1', email='test@example.com', password='123456', image='about:blank')

u.insert()

print 'new user id:', u.id

u1 = User.find_first('where email=?', 'test@example.com')
print 'find user\'s name:', u1.name

u1.delete()

u2 = User.find_first('where email=?', 'test@example.com')
print 'find user:', u2
