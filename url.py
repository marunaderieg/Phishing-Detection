import numpy as np
import urllib.parse
import warnings
import idna
import os


def _encode_puny(txt):
    """
    :param: get_visible_text that should be encoded with puny code.
    :return: Returns the given argument as ascii string. Special characters are encoded with puny.
    """
    return idna.encode(txt, uts46=True).decode('ascii')


def _decode_puny(txt):
    """
    :param txt Argument must be a ascii string which does or doesn't contain puny code.
    :return: Function decodes the punyCode parts and returns a utf-8 string.
    """
    return idna.decode(txt)


def _get_url_decoding(txt):
    """
    :param txt: the get_visible_text containing url current_encoding (ex.%20 for space)
    :return: url decoded get_visible_text in utf-8
    """
    return urllib.parse.unquote(txt)


def _get_url_encoding(txt, safe=''):
    """
    :param txt: get_visible_text that is to be url encoded (ex.%20 for space)
    :param safe: a string of all characters, that should contain their value in the url current_encoding (e.g. safe='/' in path)
    :return: url encoded get_visible_text
    """
    return urllib.parse.quote(txt, safe)


def _get_public_suffix_list(filename, puny=True):
    """
    Creates a numpy array list of all the public suffixes such as .com, co.uk, co.in, de, ...
    All entries with special characters are encoded with puny code.

    Important: update the file containing all the public suffixes once a year.
    It can be downloaded here: https://publicsuffix.org/list/

    :param filename: name of the file downloaded from https://publicsuffix.org/list/.
                     File contains all public suffixes.
    :param puny: If puny is True, all entries in the public suffix list list will be encoded with puny.
                 If puny is False, then no entry in the public suffix list will be puny encoded.
                 If puny is None, then none of the entries in the list are modified.
                 In the current version of the downloadable 'public suffic list' none of the entries
                 are encoded with puny code. However, puny code can be found in the comments of the list.
                 These comments are ignored, when the list is imported.
    """
    path = os.path.dirname(__file__)
    filepath = os.path.realpath("{0}/" + filename.format(path))
    suffix_list = np.sort(np.genfromtxt(filepath, comments='/', dtype=None, encoding=None))

    if puny is None:
        return suffix_list
    # fix all list entries that start with ! or *. because these can not be encoded in puny code
    for i in range(len(suffix_list)):
        if len(suffix_list[i]) > 1:
            if suffix_list[i][0] == '!':
                suffix_list[i] = suffix_list[i][1:]
        if len(suffix_list[i]) > 2:
            if suffix_list[i][0:2] == '*.':
                suffix_list[i] = suffix_list[i][2:]

    # Puny Encode/Decode all list. In the unexpected case of an error, delete the entry.
    i = 0
    while i < len(suffix_list):
        if len(suffix_list[i]) > 0:
            try:
                if puny:
                    suffix_list[i] = _encode_puny(suffix_list[i])
                else:
                    suffix_list[i] = _decode_puny(suffix_list[i])
                i += 1
            except idna.InvalidCodepoint:
                suffix_list = np.delete(suffix_list, i)
        else:
            suffix_list = np.delete(suffix_list, i)

    return suffix_list


def _get_query_tokens(query):
    """
    :param query: the query string that should be tokenized
    :return: the query parameters in a list of tuples ➔ example [(name1,value1),(name2,value2)
    """
    if (query is not None) and ('=' in query):
        return urllib.parse.parse_qsl(query)
    else:
        return None


def _parse_url(url, puny=None, url_encoding=None):
    """
    :param url: must be a string that represents a url. Otherwise Objects of type None are returned.
    :param puny: value is either None, False or True.
           None➔ url is neither puny encoded nor puny decoded
           True➔ url is puny encoded (e.g. "ॐNamahShivaya" will become "xn--namahshivaya-76x")
           False➔ url is puny decoded (e.g. "xn--namahshivaya-76x" will become "ॐNamahShivaya" )
    :param url_encoding: value is either None,False or True.
           None➔ url is neither url-decoded nor url-encoded
           False➔ all url-encoded characters are decoded (e.g. %20 will be converted to ' ')
           True➔ all special characters in the url which are not in the 'safe' list are url-encoded.
                  (e.g. ' ' will be converted to %20). Please note, that if a url string is first url-decoded, and
                  then url-encoded again, this will not necessarily return an identical url to the original url.
                  For example: http://mywebsite.com?name%201=weird%3Dvalue will be url-decoded to
                  http://mywebsite.com?name 1=weird=value. Because '=' is in the 'safe' list, this url would be
                  url-encoded into http://mywebsite.com?name%201=weird=value. Note that this url is different from
                  the first one.
    :return: _tokens (array with 5 fields: scheme, domain, path, query, fragment), ip, port
    """

    tokens = urllib.parse.urlsplit(url)

    # copy relevant result into array (otherwise no assignment possible)
    tokens = [tokens[0], tokens[1], tokens[2], tokens[3], tokens[4]]

    # fix1: scheme error (if no scheme provided)
    if tokens[0] == '':
        tokens = urllib.parse.urlsplit('http://' + url)
        tokens = [None, tokens[1], tokens[2], tokens[3], tokens[4]]

    # test if url is a url
    if (type(url) != str) or (' ' in tokens[1]) or ('.' not in tokens[1]) or (len(tokens[1]) > 255):
        tokens = [None, None, None, None, None, None]
        warnings.warn("given argument is not a Url")
    domain_tokens = '.'.split(tokens[1])
    for i in domain_tokens:
        if len(i) > 63:
            tokens = [None, None, None, None, None, None]
            warnings.warn("given argument is not a Url")
            break

    # fix2: replace empty strings with None
    for i in range(5):
        if tokens[i] == '':
            tokens[i] = None

    # fix3: special case: path starts with . or ..
    if tokens[1] is not None:
        if tokens[1][len(tokens[1]) - 1] == '.':
            tokens[1] = tokens[1][:len(tokens[1]) - 1]
            tokens[2] = '.' + tokens[2]
        if tokens[1][len(tokens[1]) - 1] == '.':
            tokens[1] = tokens[1][:len(tokens[1]) - 1]
            tokens[2] = '.' + tokens[2]

    # fix4: port number shows up in fqdn
    if tokens[1] is not None:
        if ':' in tokens[1]:
            split = tokens[1].split(':')
            tokens[1] = split[0]
            port = split[1]
        else:
            port = None
    else:
        port = None

    # fix5: special case: ip address:
    if tokens[1] is not None:
        if ord(tokens[1][len(tokens[1]) - 1]) <= 57 and ord(
                tokens[1][len(tokens[1]) - 1]) >= 48:
            ip = tokens[1]
            tokens[1] = None
        else:
            ip = None
    else:
        ip = None

    # Making sure the domain is in ascii code. Convert special characters to puny, if puny=True.
    if tokens[1] is not None:
        if puny:
            try:
                tokens[1] = _encode_puny(tokens[1])
            except idna.InvalidCodepoint:  # given Url was not a Url
                tokens = [None, None, None, None, None, None]
                ip = None
                port = None
        elif puny is False:
            tokens[1] = _decode_puny(tokens[1])

    # query_tokens
    query_tokens = _get_query_tokens(tokens[3])

    # decode url if url_encoding is False
    if url_encoding is False:
        if tokens[2] is not None:
            tokens[2] = _get_url_decoding(tokens[2])
        if tokens[3] is not None:
            tokens[3] = _get_url_decoding(tokens[3])
        if tokens[4] is not None:
            tokens[4] = _get_url_decoding(tokens[4])
        if query_tokens is not None:
            new_query_tokens = []
            for i in range(len(query_tokens)):
                name = _get_url_decoding(query_tokens[i][0])
                value = _get_url_decoding(query_tokens[i][1])
                new_query_tokens.append((name, value))
            query_tokens = new_query_tokens

    # decode url if url_encoding is True
    if url_encoding:
        allowed_characters = "$-_.+!*'()"
        if tokens[2] is not None:
            tokens[2] = _get_url_encoding(tokens[2], safe=allowed_characters + '/:')
        if tokens[3] is not None:
            tokens[3] = _get_url_encoding(tokens[3], safe=allowed_characters + '&/;:')
        if tokens[4] is not None:
            tokens[4] = _get_url_encoding(tokens[4], safe=allowed_characters + '#&/;:')
        if query_tokens is not None:
            new_query_tokens = []
            for i in range(len(query_tokens)):
                name = _get_url_encoding(query_tokens[i][0])
                value = _get_url_encoding(query_tokens[i][1])
                new_query_tokens.append((name, value))
            query_tokens = new_query_tokens

    return tokens, ip, port, query_tokens


class Url:
    """
    Important: update the file public_suffix_list.dat once a year.
    That's where it's from: https://publicsuffix.org/list/

    Url Objects have the following attributes and methods:

    passed parameters attributes:
    ●  original_url ➔ value of passed parameter
    ●  www_ignore ➔ value of passed parameter
    ●  puny ➔ value of passed parameter
    ●  url_encoding ➔ value of passed parameter

    parsed url attributes:
    ●  url
    ●  scheme ➔ e.g. 'http'
    ●  fqdn ➔ full qualifying domain name (in case an ip address is given instead of the domain name, the fqdn is None)
    ●  fqdn_tokens  ➔ list of all _tokens in the fqdn
    ●  ip ➔ ip address, if specified in the url instead of a fqdn
    ●  port ➔ the port used, if specified in the url (most of the time this attribute is None)
    ●  path ➔ path where the requested html file is located on the server
    ●  query ➔ parameters passed to the server
    ●  query_tokens ➔ tokenized parameters in tuple form.
    ●  fragment ➔ anchor
    ➔ example: url='https://mywebsite.com:443/my/path.html?name1=value1&name2=value2#iAmAnFragment
      scheme='https', fqdn='mywebsite.com', fqdn_tokens=['mywebsite','com'], ip=None, port=443, path='/my/path.html',
      query='name1=value1&name2=value2', query_tokens='((name1,value1),(name2,value2)), fragment='iAmAnFragment'

    parsed domain attributes:
    ●  sd ➔ subdomains
    ●  sd_tokens ➔ tokenized subdomains
    ●  nr_sub_domains ➔ number of subdomains
    ●  www ➔ true, if www is the first subdomain in the passed url
    ●  mld ➔ main level domain
    ●  tld ➔ top level domain
    ●  tld_tokens ➔ tokenized top level domain
    ●  rdn ➔ registered domain name = mld+tld
    ●  rdn_tokens ➔ tokenized registered domain name
    ➔ example: url='https://www.my.awesome.website.co.uk'
      sd='www.my.awesome', sd_tokens=['www','my','awesome'], nr_sub_domains=3, www=True, mld='website', tld='co.uk',
      tld_tokens=['co','uk'], rdn='website.co.uk', rdn_tokens=['website','co','uk']

    class attribute:
    ●  public_suffix_list ➔ alphabetically sorted numpy array containing all currently available top level domains.
                            All list entries which contain non ascii characters are puny encoded.
    dynamic methods:
    ●  free_url()
    ●  free_url_tokens()
    ●  rdn_in_sd()
    ●  rdn_in_path()

    static methods:
    ● mld_of_tld()
    ● decode_puny()
    ● encode_puny()
    ● url_decoding()
    ● url_encoding()
    ● parse_url()
    ● get_public_suffix_list()
    """

    public_suffix_list = _get_public_suffix_list("../public_suffix_list.dat")

    def __init__(self, url, www_ignore=False, puny=True, url_encoding=None):

        self.original_url = url
        self.www_ignore = www_ignore
        self.puny = puny
        self.url_encoding = url_encoding
        self._tokens, self.ip, self.port, self.query_tokens = _parse_url(url.strip(), puny=True,
                                                                         url_encoding=self.url_encoding)
        # set 'private' variable self._return_decoded_puny in order to know later whether the attributes have to be
        # initialized with puny current_encoding or not
        if (self.puny is None) and (self._tokens[1] is not None):
            domain = urllib.parse.urlsplit(url)[1]
            if ('xn--' in _encode_puny(domain)) and ('xn--' not in domain):
                self._return_decoded_puny = True
            else:
                self._return_decoded_puny = False
        else:
            self._return_decoded_puny = not self.puny

        # parsing of the domain name

        # fqdn=full qualifying domain name
        self.fqdn = self._tokens[1]
        if self.fqdn is not None:
            self.fqdn_tokens = self.fqdn.split('.')
        else:
            self.fqdn_tokens = None

        # mld,tld -> mld=main level domain, tld=top level domains
        if self.fqdn_tokens is not None:
            i = 1
            while i < len(self.fqdn_tokens):
                if '.'.join(self.fqdn_tokens[i:len(self.fqdn_tokens)]) in Url.public_suffix_list:
                    self.mld = self.fqdn_tokens[i - 1]
                    self.tld_tokens = self.fqdn_tokens[i:]
                    self.tld = '.'.join(self.tld_tokens)
                    break
                else:
                    i = i + 1
            if i == len(self.fqdn_tokens):  # tld was not in Url.public_suffix_list
                self.mld = self.fqdn_tokens[len(self.fqdn_tokens) - 2]
                self.tld = self.fqdn_tokens[len(self.fqdn_tokens) - 1]
                self.tld_tokens = [self.tld]
        else:
            self.mld = None
            self.tld = None
            self.tld_tokens = None

        # decode Punycode
        if self._return_decoded_puny and (self._tokens[1] is not None):
            if self.mld is not None:
                self.mld = _decode_puny(self.mld)
            self.tld = _decode_puny(self.tld)
            self.tld_tokens = self.tld.split('.')
            self._tokens[1] = _decode_puny(self._tokens[1])
            self.fqdn = _decode_puny(self.fqdn)
            self.fqdn_tokens = self.fqdn.split('.')

        # rdn = registered domain name
        if self.mld is not None:
            self.rdn = self.mld + '.' + self.tld
            self.rdn_tokens = self.rdn.split('.')
        else:
            self.rdn = None
            self.rdn_tokens = None

        # number of Subdomains
        if (self.fqdn_tokens is not None) and (self.rdn_tokens is not None):
            self.nr_sub_domains = len(self.fqdn_tokens) - len(self.rdn_tokens)
        else:
            self.nr_sub_domains = 0

        # www_ignore and www=True if the subdomains start with 'www'
        self.www = False
        if (self.fqdn_tokens is not None) and (self.nr_sub_domains > 0):
            if self.fqdn_tokens[0] == 'www':
                self.www = True
            if self.www_ignore and self.www:
                self.fqdn_tokens = self.fqdn_tokens[1:]
                self.fqdn = '.'.join(self.fqdn_tokens)
                self.nr_sub_domains -= 1

        # sd = subdomains
        if (self.fqdn_tokens is not None) and (self.rdn_tokens is not None):
            if self.nr_sub_domains > 0:
                self.sd_tokens = self.fqdn_tokens[:self.nr_sub_domains]
                self.sd = ".".join(self.sd_tokens)
            else:
                self.sd_tokens = None
                self.sd = None
        else:
            self.sd_tokens = None
            self.sd = None

        # url
        self.url = ''
        if self._tokens[0] is not None:
            self.url += self._tokens[0] + '://'
        if self._tokens[1] is not None:
            self.url += self._tokens[1]
        elif self.ip is not None:
            self.url += self.ip
        if self.port is not None:
            self.url += ':' + self.port
        if self._tokens[2] is not None:
            self.url += self._tokens[2]
        if self._tokens[3] is not None:
            self.url += '?' + self._tokens[3]
        if self._tokens[4] is not None:
            self.url += '#' + self._tokens[4]
        if self.url == '':
            self.url = None

        # other parts of Url
        self.scheme = self._tokens[0]
        self.path = self._tokens[2]
        self.query = self._tokens[3]
        self.fragment = self._tokens[4]

    def rdn_in_sd(self):
        """
        Tests, if a registered domain (e.g.'maruna.org') shows up in the subdomains.
        This would indicate a obfuscation technique.
        :return: registered domain name which shows up in the path. Otherwise None.
        """
        if self.sd_tokens is not None:
            # make sure subdomains is in puny, so that tld can be found in public suffix list
            if self._return_decoded_puny:
                subdomains = _encode_puny(self.sd)
            else:
                subdomains = self.sd
            # for each entry in public suffix list check, if it is present in the subdomains. Take the longest entry.
            tld = ''
            for i in Url.public_suffix_list:
                if '.' + i + '.' in subdomains + '.':
                    if len(tld) < len(i):
                        tld = i
            # find the mld which belongs to the found tld. Decode results, in case the sd was puny encoded earlier.
            if tld != '':
                mld = Url.mld_of_tld(subdomains, tld)
                if self._return_decoded_puny:
                    mld = _decode_puny(mld)
                    tld = _decode_puny(tld)
                return mld + '.' + tld
        return None

    def rdn_in_path(self):
        """
        Tests, if a registered domain name (e.g. maruna.org) shows up in the path.
        This would indicate a obfuscation technique.
        :return: registered domain name which shows up in the path. Otherwise None.
        """
        if self.path is not None:
            tld = ''
            for character in [' ', '/', '?', '#', ';', '.']:
                for i in Url.public_suffix_list:
                    if '.' + i + character in self.path + character:
                        if len(tld) < len(i):
                            tld = i
                if tld != '':
                    break
            if tld != '':
                mld = Url.mld_of_tld(self.path, tld)
                rdn = mld + '.' + tld
                return rdn
        return None

    def free_url_tokens(self):
        """
        the free url is the part of the url, which can be choosen freely, whereas the registered domain part is subject
        to avaiability ➔ e.g. bank.com cannot be chosen as registered domain, since it already exists, but
        bank.com.my-new-website-with-unique-name.com on the otherhand is possible, since here 'bank.com' is in the
        'free url' part. Likewise path, querystring and fragment can be choosen freely.
        :return: list with 4 entries: [subdomains,path,query,fragment]. Entry will be None if not existing.
        """
        free_url_tokens = self._tokens[1:]
        free_url_tokens[0] = self.sd
        return free_url_tokens

    def free_url(self):
        """
        the free url is the part of the url, which can be choosen freely, whereas the registered domain part is subject
        to avaiability ➔ e.g. bank.com cannot be chosen as registered domain, since it already exists, but
        bank.com.my-new-website-with-unique-name.com on the otherhand is possible, since here 'bank.com' is in the
        'free url' part. Likewise path, querystring and fragment can be choosen freely.
        :return subdomains + path + query + fragment
        """
        free_url_tokens = self.free_url_tokens()
        free_url = ""
        if free_url_tokens[0] is not None:
            free_url += free_url_tokens[0]
        if free_url_tokens[1] is not None:
            free_url += free_url_tokens[1]
        if free_url_tokens[2] is not None:
            free_url += ';' + free_url_tokens[2]
        if free_url_tokens[3] is not None:
            free_url += '?' + free_url_tokens[3]
        if free_url_tokens[4] is not None:
            free_url += '#' + free_url_tokens[4]
        if free_url == "":
            free_url = None
        return free_url, free_url_tokens

    @staticmethod
    def mld_of_tld(text, tld):
        """
        :param text: a string which contains a registered domain
        ➔ example: 'I am a random string...maruna.org...some more string'
        :param tld: a top level domain (tld) name that exists in the 'public suffix list'
        :return: the main level domain (mld) which belongs to the given top level domain (tld)
        ➔ example: if the string above is given as 'get_visible_text', then the returned mld will be 'maruna'
        """
        if '.' + tld not in text:
            return None
        text = text.split('.' + tld)[0][::-1]
        j = -1
        for i in text:
            j += 1
            if (ord(i) != 45) and ((ord(i) < 65) or (ord(i) > 122)) and (
                    (ord(i) < 48) or (ord(i) > 57)):  # i is a character not allowed in domain names
                break
        if j == len(text) - 1:
            mld = text
        else:
            mld = text[:j]
        if len(mld) < 2:
            return None
        if len(mld) > 63:
            mld = mld[:63]
        if mld[0] == '-':  # domain name can't start or end with a '-'
            mld = mld[1:]
        mld = mld[::-1]
        if mld[0] == '-':
            mld = mld[1:]
        return mld

    @staticmethod
    def decode_puny(text):
        """
        :param domain name containing puny code
        :return: decoded domain name, as a utf-8 string
        """
        return _decode_puny(text)

    @staticmethod
    def encode_puny(text):
        """
        :param: domain name that should be encoded with puny code.
        :return: Ascii string. Special characters are encoded with puny.
        """
        return _encode_puny(text)

    @staticmethod
    def url_decoding(text):
        """
        :param text: the get_visible_text containing url current_encoding (ex.%20 for space)
        :return: url decoded get_visible_text in utf-8
        """
        return _get_url_decoding(text)

    @staticmethod
    def url_encoding(text, safe=''):
        """
        :param text: get_visible_text that is to be url encoded (ex.%20 for space)
        :param safe: a string of all characters, that will not be url encoded (e.g. safe='/' in path)
        :return: url encoded get_visible_text
        """
        return _get_url_encoding(text, safe)

    @staticmethod
    def parse_url(url, puny=None, url_encoding=None):
        """
        :param url: must be a string that represents a url. Otherwise Objects of type None are returned.
        :param puny: value is either None, False or True.
               None➔ url is neither puny encoded nor puny decoded
               True➔ url is puny encoded (e.g. "ॐNamahShivaya" will become "xn--namahshivaya-76x")
               False➔ url is puny decoded (e.g. "xn--namahshivaya-76x" will become "ॐNamahShivaya" )
        :param url_encoding: value is either None,False or True.
               None➔ url is neither url-decoded nor url-encoded
               False➔ all url-encoded characters are decoded (e.g. %20 will be converted to ' ')
               True➔ all special characters in the url which are not in the 'safe' list are url-encoded.
                      (e.g. ' ' will be converted to %20). Please note, that if a url string is first url-decoded, and
                      then url-encoded again, this will not necessarily return an identical url to the original url.
                      For example: http://mywebsite.com?name%201=weird%3Dvalue will be url-decoded to
                      http://mywebsite.com?name 1=weird=value. Because '=' is in the 'safe' list, this url would be
                      url-encoded into http://mywebsite.com?name%201=weird=value. Note that this url is different from
                      the first one.
        :return: _tokens (array with 5 fields: scheme, domain, path, query, fragment), ip, port
        """
        return _parse_url(url, puny, url_encoding)

    @staticmethod
    def get_public_suffix_list(filename, puny=True):
        """
        Creates a numpy array list of all the public suffixes such as .com, co.uk, co.in, de, ...
        All entries with special characters are encoded with puny code.

        Important: update the file containing all the public suffixes once a year.
        It can be downloaded here: https://publicsuffix.org/list/

        ;param filename: name of the file downloaded from https://publicsuffix.org/list/.
                         File contains all public suffixes.
        ;param puny: If puny is True, all entries in the public suffix list list will be encoded with puny.
                     If puny is False, then no entry in the public suffix list will be puny encoded.
                     If puny is None, then none of the entries in the list are modified.
                     In the current version of the downloadable 'public suffic list' none of the entries
                     are encoded with puny code. However, puny code can be found in the comments of the list.
                     These comments are ignored, when the list is imported.
        """
        return _get_public_suffix_list(filename, puny)
