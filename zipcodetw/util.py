#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

class Address(object):

    TOKEN_RE = re.compile(u'''
        (?:
            (?P<no>\d+)
            (?P<subno>之\d+)?
            (?=[巷弄號樓])
            |
            (?P<name>.+?)
        )
        (?:
            (?P<unit>[縣市鄉鎮市區村里鄰路段街巷弄號樓])
            |
            (?=\d+(?:[之-]\d+)?[巷弄號樓]|$)
        )
    ''', re.X)

    NO    = 0
    SUBNO = 1
    NAME  = 2
    UNIT  = 3

    UNITS_0 = u'縣市'
    UNITS_2 = u'里鄰路段街'

    TO_REPLACE_RE = re.compile(u'''
    [ 　,，台-]
    |
    [０-９]
    |
    [一二三四五六七八九]?
    十?
    [一二三四五六七八九]
    (?=[段路街巷弄號樓])
    ''', re.X)

    TO_REMOVE_SET = set(u' 　,，')

    TO_REPLACE_MAP = {
        u'-' : u'之', u'台': u'臺',
        u'一': u'1', u'二': u'2', u'三': u'3', u'四': u'4', u'五': u'5',
        u'六': u'6', u'七': u'7', u'八': u'8', u'九': u'9',
    }

    @staticmethod
    def normalize(s):

        if isinstance(s, str):
            s = s.decode('utf-8')

        def replace(m):

            found = m.group()

            if found in Address.TO_REMOVE_SET:
                return u''
            if found in Address.TO_REPLACE_MAP:
                return Address.TO_REPLACE_MAP[found]

            len_found = len(found)

            # 65296 = '０'; 65305 = '９'; 65248 = '０'-'0'
            if len_found == 1 and 65296 <= ord(found) <= 65305:
                return unichr(ord(found)-65248)

            # for '十一' to '九十九'
            if len_found == 2:
                return u'1'+Address.TO_REPLACE_MAP[found[1]]
            if len_found == 3:
                return Address.TO_REPLACE_MAP[found[0]]+Address.TO_REPLACE_MAP[found[2]]

        s = Address.TO_REPLACE_RE.sub(replace, s)

        return s

    TO_INGORE = set(u'鄰里')

    @staticmethod
    def tokenize(addr_str):

        tokens = Address.TOKEN_RE.findall(Address.normalize(addr_str))

        # remove tokens whose unit is in TO_INGORE

        len_tokens = len(tokens)

        i = 2
        while i < len_tokens:
            name = tokens[i][Address.NAME]
            unit = tokens[i][Address.UNIT]
            if unit and unit in Address.TO_INGORE and name != u'宮后':
                del tokens[i]
                len_tokens -= 1
            else:
                i += 1

        return tuple(tokens)

    def __init__(self, str_or_tokens):
        if isinstance(str_or_tokens, (tuple, list)):
            tokens = str_or_tokens
        else:
            tokens = Address.tokenize(str_or_tokens)
        self.tokens = tokens

    def __len__(self):
        return len(self.tokens)

    def __getitem__(self, val):
        try:
            return self.tokens[val]
        except IndexError:
            return (u'', u'')

    def flat(self, sarg=None, *sargs):
        return u''.join(u''.join(token) for token in self.tokens[slice(sarg, *sargs)])

    def pick_to_flat(self, *idxs):
        return u''.join(u''.join(self.tokens[idx]) for idx in idxs)

    def __repr__(self):
        return 'Address(%r)' % self.flat()

    def parse(self, idx):
        try:
            token = self.tokens[idx]
        except IndexError:
            return (0, 0)
        else:
            return (
                int(token[Address.NO]        or 0),
                int(token[Address.SUBNO][1:] or 0)
            )

class Rule(Address):

    RULE_TOKEN_RE = re.compile(u'''
        及以上附號|含附號以下|含附號全|含附號
        |
        以下|以上
        |
        附號全
        |
        [連至單雙全](?=[\d全]|$)
    ''', re.X)

    @staticmethod
    def part(rule_str):

        rule_str = Address.normalize(rule_str)

        rule_tokens = set()

        def extract(m):

            token = m.group()
            retval = u''

            if token == u'連':
                token = u''
            elif token == u'附號全':
                retval = u'號'

            if token:
                rule_tokens.add(token)

            return retval

        addr_str = Rule.RULE_TOKEN_RE.sub(extract, rule_str)

        return (rule_tokens, addr_str)

    def __init__(self, rule_str):
        self.rule_tokens, addr_str = Rule.part(rule_str)
        Address.__init__(self, addr_str)

    def __repr__(self):
        return 'Rule(%r)' % (self.flat()+u''.join(self.rule_tokens))

    def match(self, addr):

        # except tokens reserved for rule token

        my_last_pos = len(self.tokens)-1
        my_last_pos -= bool(self.rule_tokens) and u'全' not in self.rule_tokens
        my_last_pos -= u'至' in self.rule_tokens

        # Attempts to fill a level-1 token if the input address lacks one.

        addr_tokens = [t for t in addr.tokens]
        if (len(addr_tokens) > 1
                and addr_tokens[0][Address.UNIT] in Address.UNITS_0
                and addr_tokens[1][Address.UNIT] in Address.UNITS_2):
            addr_tokens.insert(1, self.tokens[1])
            addr = Address(addr_tokens)

        # tokens must be matched exactly

        if my_last_pos >= len(addr.tokens):
            return False

        i = my_last_pos
        while i >= 0:
            if self.tokens[i] != addr.tokens[i]:
                return False
            i -= 1

        # check the rule tokens

        his_no_pair     = addr.parse(my_last_pos+1)
        if self.rule_tokens and his_no_pair == (0, 0):
            return False

        my_no_pair      = self.parse(-1)
        my_asst_no_pair = self.parse(-2)
        for rt in self.rule_tokens:
            if (
                (rt == u'單'         and not his_no_pair[0] & 1 == 1) or
                (rt == u'雙'         and not his_no_pair[0] & 1 == 0) or
                (rt == u'以上'       and not his_no_pair >= my_no_pair) or
                (rt == u'以下'       and not his_no_pair <= my_no_pair) or
                (rt == u'至'         and not (
                    my_asst_no_pair <= his_no_pair <= my_no_pair or
                    u'含附號全' in self.rule_tokens and his_no_pair[0] == my_no_pair[0]
                )) or
                (rt == u'含附號'     and not  his_no_pair[0] == my_no_pair[0]) or
                (rt == u'附號全'     and not (his_no_pair[0] == my_no_pair[0] and his_no_pair[1] > 0)) or
                (rt == u'及以上附號' and not  his_no_pair >= my_no_pair) or
                (rt == u'含附號以下' and not (his_no_pair <= my_no_pair  or his_no_pair[0] == my_no_pair[0]))
            ):
                return False

        return True

import sqlite3
import csv
from functools import wraps

class Directory(object):

    @staticmethod
    def get_common_part(str_a, str_b):

        if str_a is None: return str_b
        if str_b is None: return str_a

        i = 0 # for the case range is empty
        for i in range(min(len(str_a), len(str_b))):
            if str_a[i] != str_b[i]:
                break
        else:
            i += 1

        return str_a[:i]

    def __init__(self, db_path, keep_alive=False):
        self.db_path = db_path
        # It will always use a same connection if keep_alive is true.
        self.keep_alive = keep_alive
        self.conn = None
        self.cur = None

    def create_tables(self):

        # Division levels for an address:
        # 0. 直轄市, 縣
        # 1. 區, 縣轄市, 鄉鎮 etc.
        # 2. 路, 街 (含段)
        # 3. 其他部分
        self.cur.execute('''
            create table precise (
                addr_0 text,
                addr_1 text,
                addr_2 text,
                addr_3 text,
                rule_str text,
                zipcode  text,
                primary key (addr_0, addr_1, addr_2, addr_3, rule_str)
            );
        ''')

        self.cur.execute('''
            create table gradual (
                addr_str text primary key,
                zipcode  text
            );
        ''')

    def put_precise(self, addr, rule_str, zipcode):

        self.cur.execute('''
            insert or ignore into precise values (?, ?, ?, ?, ?, ?);
        ''', (
            ''.join(addr[0]),
            ''.join(addr[1]),
            ''.join(addr[2]),
            ''.join(addr[3]),
            rule_str,
            zipcode
        ))

        return self.cur.rowcount

    def put_gradual(self, addr_str, zipcode):

        self.cur.execute('''
            select zipcode
            from   gradual
            where  addr_str = ?;
        ''', (addr_str,))

        row = self.cur.fetchone()
        if row is None:
            stored_zipcode = None
        else:
            stored_zipcode = row[0]

        self.cur.execute('replace into gradual values (?, ?);', (
            addr_str,
            Directory.get_common_part(stored_zipcode, zipcode),
        ))

        return self.cur.rowcount

    def put(self, head_addr_str, tail_rule_str, zipcode):

        addr = Address(head_addr_str)

        # (a, b, c)

        self.put_precise(
            addr,
            head_addr_str+tail_rule_str,
            zipcode
        )

        # (a, b, c) -> (a,); (a, b); (a, b, c); (b,); (b, c); (c,)

        len_tokens = len(addr)
        for f in range(len_tokens):
            for l in range(f, len_tokens):
                self.put_gradual(
                    addr.flat(f, l+1),
                    zipcode
                )

        if len_tokens >= 3:
            self.put_gradual(addr.pick_to_flat(0, 2), zipcode)

    def within_a_transaction(method):

        @wraps(method)
        def method_wrapper(self, *args, **kargs):

            if not self.keep_alive or self.conn is None:
                self.conn = sqlite3.connect(self.db_path)
            self.cur = self.conn.cursor()

            try:
                retval = method(self, *args, **kargs)
            except:
                self.conn.rollback()
                raise
            else:
                self.conn.commit()
            finally:
                self.cur.close()
                if not self.keep_alive:
                    self.conn.close()

            return retval

        return method_wrapper

    @within_a_transaction
    def load_chp_csv(self, chp_csv_lines):

        self.create_tables()

        lines_iter = iter(chp_csv_lines)
        next(lines_iter)

        for row in csv.reader(lines_iter):
            self.put(
                ''.join(row[1:-1]).decode('utf-8'),
                row[-1].decode('utf-8'),
                row[0].decode('utf-8'),
            )

    def get_rule_str_zipcode_pairs(self, addr, *sargs):

        where_params = ([], [])

        level = 0
        tokens = addr.tokens[slice(*sargs)]
        while level < min(4, len(tokens)):
            token = tokens[level]
            if level == 1 and token[Address.UNIT] in Address.UNITS_2:
                level += 1
            where_params[0].append('addr_%d = ?' % level)
            where_params[1].append(''.join(token))
            level += 1

        query = '''
            select rule_str, zipcode
            from   precise
            where  %s;
        ''' % (' and '.join(where_params[0]))

        self.cur.execute(query, where_params[1])

        return self.cur.fetchall()

    def get_gradual_zipcode(self, addr, *sargs):

        self.cur.execute('''
            select zipcode
            from   gradual
            where  addr_str = ?;
        ''', (addr.flat(*sargs),))

        row = self.cur.fetchone()
        return row and row[0] or None

    @within_a_transaction
    def find(self, addr_str):

        addr = Address(addr_str)

        for i in range(len(addr.tokens), 0, -1):
            rzpairs = self.get_rule_str_zipcode_pairs(addr, i)
            if rzpairs:
                match = None
                for rule_str, zipcode in rzpairs:
                    if Rule(rule_str).match(addr):
                        if match:   # Multiple matches found. Failed.
                            break
                        match = zipcode
                else:
                    if match:
                        return match
            gzipcode = self.get_gradual_zipcode(addr, i)
            if gzipcode:
                return gzipcode

        return u''
