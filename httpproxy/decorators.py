import re

from django.core.urlresolvers import reverse
from urlparse import urljoin
import urllib

# Replace links in the HTML code
REWRITE_HTML_REGEX = re.compile(r'((?:src|action|href)=["\'])(.*?)(["\'])', 
    re.IGNORECASE)
# Replace links in the CSS files
REWRITE_STYLES_REGEX = re.compile(r'((?:url)\(["\'])(.*?)(["\']\))',
    re.IGNORECASE)


def rewrite_response(fn, base_url, proxy_view_name):
    def fix_relative_url(url):
        if not url.startswith('javascript:') and not url.startswith('#'):
            return urllib.quote(urljoin(base_url, url), safe=':=&;/')
        return url
    """
    Rewrites the response to fix references to resources loaded from HTML
    files (images, etc.).
    """
    def decorate(request, *args, **kwargs):
        response = fn(request, *args, **kwargs)
        proxy_root = reverse(proxy_view_name,
            kwargs={'url': ''}
        )
        def replace_links(match):
            href = match.group(1)
            link_url = fix_relative_url(match.group(2))
            quotes = match.group(3)
            return (href + proxy_root + link_url + quotes) \
                .encode(response._charset)
        response.content = REWRITE_HTML_REGEX.sub(replace_links, 
            response.content)
        response.content = REWRITE_STYLES_REGEX.sub(replace_links,
            response.content)
        return response

    return decorate
