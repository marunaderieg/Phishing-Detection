import requests
import requests.adapters
import datetime
import warnings
from urllib3.util import retry
from bs4 import BeautifulSoup


def _get_visible_text(bs_object):
    # delete all script and style elements
    for script in bs_object(["script", "style"]):
        script.extract()
    # get get_visible_text
    text = bs_object.get_text()
    # break into lines and remove leading and trailing space on each
    lines = (line.strip() for line in text.splitlines())
    # break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # drop blank lines
    text = '\n'.join(chunk for chunk in chunks if chunk)
    return str(text)


class Webpage:
    """
    Webpage objects have the following attributes and methods:

    Attributes:
        ●  starting_url ➔ the url that was passed in a request. Value will be None if not provided.
        ●  landing_url ➔ the last url in the redirection chain. If there are no redirections,
           then starting url and landing url are identical. Value will be None if not provided.
        ●  date_time ➔ date and time when webpage was loaded. Value will be None if not provided.
        ●  html ➔ passed html
        ●  requests_object ➔ the result object if a webpage is loaded using the requests module.
           Value will be None if not provided.
        ●  soup_object ➔ beautiful soup object

    Parsed HTML Attributes:
        ●  title ➔ title of webpage
        ●  defined_encoding ➔ the encoding defined in the html
        ●  current_encoding ➔ current encoding of the html text. If no request object is passed to the constructor, this
           value is set to None. Because the encoding can only be known or changed, if a request object is passed.
        ●  visible_text ➔ string of the visible text
        ●  forms ➔ list of all forms (including tags)
        ●  images ➔ list of all image references (including tags)
        ●  images_in_forms ➔ list of all images references present in a form (including tags)
        ●  javascript ➔ list of all javascript code (including tag)
        ●  logged_links ➔ list of all logged links. Logged links are present, if there is embedded content in iframes,
           or if a href link points to a iframe (in that case the href link is classified as logged link).
        ●  href_links ➔ list of all href links
        ●  iframes ➔ list of all iframes (including tags)

    static methods:
        ●  Webpage.tokenize()
        ●  Webpage.get_visible_text()

    alternative constructor:
        ●  Webpage.from_url
           ➔ the attributes starting_url, landing_url, date_time, html and request object are automatically initialized
    """

    def __init__(self, html, starting_url=None, landing_url=None, date_time=None, requests_object=None, encoding=None):
        """
        :param html: string of the html text
        :param starting_url: url passed in the request in order to load the url. In case of redirections, the landing
               url be diffrent from the starting url.
        :param landing_url: destination url from which the page was loaded.
        :param date_time: date and time when the page was loaded
        :param requests_object: the returned requests object, in case the page was loaded with the requests module
        :param encoding: this value should be either a Boolean or a String
               if True: the html will be encoded with the encoding that is defined in the html
               if None or False: no changes are made at the html
               if String: html is encoded with the specified encoding. In case the specified encoding doesn't
                          exist, the default encoding utf-8 is applied.
               ➔ Important: encoding can only be done, if the requests object is passed to the constructor. If no
                request object is passed, then any specified encoding will be ignored.
        """

        # raise warning if current_encoding is not boolean or string
        if (type(encoding) is not bool) and (type(encoding) is not str):
            encoding = None
            warnings.warn('The current_encoding argument should be of type boolean or string. Value has been set to None.')

        # initialize attributes
        self.html = str(html)
        self.date_time = date_time   # date and time when page was loaded
        self.requests_object = requests_object
        self.starting_url = starting_url
        self.landing_url = landing_url
        if (self.landing_url is None) and (self.requests_object is not None):
            self.landing_url = self.requests_object.url

        self.soup_object = BeautifulSoup(self.html, features='html.parser')

        # initialize defined_encoding
        self.defined_encoding = None
        meta_and_charset = self.soup_object.find_all('meta', charset=True)
        if len(meta_and_charset) > 0:
            self.defined_encoding = meta_and_charset[0].get('charset')

        # initialize current_encoding. Self.current_encoding is either the specified encoding or None.
        if self.requests_object is None:
            self.current_encoding = None
        elif encoding is True:
            self.current_encoding = self.defined_encoding
        elif (encoding is False) or (encoding is None):
            self.current_encoding = None
        else:
            self.current_encoding = encoding

        # change current_encoding if necessary
        if self.requests_object is not None:
            if self.current_encoding is not None:
                if self.requests_object.encoding != self.current_encoding:
                    request_copy = self.requests_object
                    request_copy.encoding = self.current_encoding
                    self.html = request_copy.text
                    self.soup_object = BeautifulSoup(self.html, features='html.parser')
            else:
                self.current_encoding = self.requests_object.encoding

        # initialize attributes
        self.visible_text = _get_visible_text(self.soup_object)
        self.forms = self.soup_object.find_all('form')
        self.javascript = self.soup_object.find_all('script')

        # initialize images
        self.images = self.soup_object.find_all('img')
        self.images_in_forms = []
        for form in self.forms:
            images = form.find_all('img')
            for image in images:
                self.images_in_forms.append(image)

        # initialize title
        try:
            self.title = self.soup_object.title.string
        except AttributeError:
            self.title = None

        # initialize href links
        self._tags_with_href = self.soup_object.find_all(href=True)
        self.href_links = []
        for tag in self._tags_with_href:
            link = tag.get('href')
            if '://' in link:
                self.href_links.append(str(link))


        # initialize logged links
        self.iframes = self.soup_object.find_all('iframe')
        iframe_tags_with_src = self.soup_object.find_all('iframe', src=True)
        self.logged_links = []
        for tag in iframe_tags_with_src:
            link = tag.get('src')
            if '://' in link:
                self.logged_links.append(str(link))
            elif len(link) > 2:
                if link[:2] == '//':
                    self.href_links.append('http:'+str(link))

        # special case: href link points to iframe
        href_with_target = self.soup_object.find_all(href=True, target=True)
        if href_with_target is not None:
            # get a list with all iframe ids
            iframe_names = []
            for tag in self.iframes:
                iframe_names.append(tag.get('name'))
                iframe_names.append(tag.get('id'))
            # check for each entry of href_with_target if it points to a iframe id
            for tag in href_with_target:
                if tag.get('target') in iframe_names:
                    self.logged_links.append(str(tag.get('href')))
                    self.href_links.remove(str(tag.get('href')))

    @staticmethod
    def get_visible_text(soup):
        """
        :param soup: takes as an argument a beautiful soup object. In case a selected part of the html is passed,
        (for example self.forms or any result from a soup.find_all method), then one has to remember that this
        would be a list, and thus a specific item of this list has to selected
        ➔ e.g. Webpage.get_text(self.forms[0]) would pass the first form in the html
        ➔ e.g. Webpage.get_text(self.forms) would return an error
        :return: returns the visible parts of the beautiful soup object as a string
        """
        return _get_visible_text(soup)

    @staticmethod
    def tokenize(string, minimal_length=3, mapping=('', ''), include='', no_capital=True):
        """
        This function takes a string as an input and returns an array of all _tokens present
        in the string. A token is defined as follows:
        1a. all special characters that are used in languages with latin letters are mapped to
        a simplified character ➔ e.g. ä becomes a, é becomes e, and so on
        1b. all capital letters are mapped to the corresponding non-capital letter
        3. split the string whenever a character shows up, which is not in the range a-z
        4. throw away all _tokens which are of length smaller than x=3
        :param string: the string to be tokenized
        :param minimal_length: all _tokens which are smaller than the minimal length will be eliminated
        :param mapping: if mapping=(('a','äÄ'),('o','öÖ'),('u','Üü'))  then all 'ä' and 'Ä'
               characters will be mapped to 'a', all 'ö' and 'Ö' characters will be mapped to 'o', ....
        :param include: if include='äöü', then the special characters 'ä', 'ö' and 'ü' will be considered equal to any
               character in the range a-z
        :param no_capital: if set to True, all capital letters will be mapped to their eqivalent non-capital counterpart
                ➔ careful, this mapping is only done with the letters A-Z, not with special Characters
        :return: array with all _tokens
        """

        def replace(character, _mapping, _include):
            if 97 <= ord(character) <= 122:  # non-capital letter in range a-z
                return character
            elif no_capital:
                if 65 <= ord(character) <= 90:  # Capital letter in range A-Z
                    return chr(ord(character)+32)
            elif no_capital is False:
                if 65 <= ord(character) <= 90:  # Capital letter in range A-Z
                    return character
            elif character in _include:
                return character
            for tupel in _mapping:
                if character in tupel[1]:
                    return tupel[0]
            return ' '

        # exchange each character in the string with the corresponding character
        # of the chosen mapping

        # TODO : This could be really slow, may need to be optimized.

        tokens = ''
        for char in string:
            tokens += replace(char, mapping, include)
        tokens = tokens.split(' ')

        # remove all _tokens who are shorter than minimal length
        i = 0
        while i < len(tokens):
            if len(tokens[i]) < minimal_length:
                del tokens[i]
            else:
                i += 1

        return tokens

    @classmethod
    def from_url(cls, starting_url, encoding=None):
        """
        This is an alternative constructor. Instead of passing a html, one can use this
        constructor to create a Webpage object from a url. The corresponding soup object will
        then be loaded. Note, that this will only work if there is internet connection and if the Webserver
        belonging to the passed Url is reachable.
        :param starting_url: the url from which the webpage is loaded.
        :param encoding: this value should be either a Boolean or a String
               if True: the html will be encoded with the encoding that is defined in the html
               if None or False: no changes are made at the html
               if String: html is encoded with the specified encoding. In case the specified encoding doesn't
                          exist, the default encoding utf-8 is applied.
        :return: a Webpage object, where the attributes starting_url, landing_url, date_time, html and request object
               are automatically initialized.
        """
        # add defaulte scheme
        if '://' not in starting_url:
            starting_url = 'http://' + starting_url

        # get requests object
        try:
            r = requests.get(starting_url, verify=False, timeout=20)
        except retry.MaxRetryError:
            warnings.warn('Webpage could not be loaded, because there is a MaxRetryError". Constructor returned None.')
            return Webpage(None)
        except requests.adapters.SSLError:
            warnings.warn('Webpage could not be loaded, because there is a "SSLError". You might be using ' 
                          'https for a website, that is not using SSL. Constructor returned None.')
            return None
        except requests.adapters.ConnectionError:
            warnings.warn('Webpage could not be loaded, because there is a "ConnectionError". The page '
                          'you are trying to laod might not be on the server anymore. Constructor returned None.')
            return None
        except:
            warnings.warn('Webpage could not be loaded. Constructor returned None.')
            return None

        # initialize attributes
        now = datetime.datetime.now()
        landing_url = r.url
        html = r.text

        return Webpage(html, starting_url=starting_url, landing_url=landing_url, date_time=now,
                       requests_object=r, encoding=encoding)
