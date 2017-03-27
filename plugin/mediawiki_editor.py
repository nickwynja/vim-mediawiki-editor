import sys, os, os.path


try:
    import mwclient
    import ConfigParser
except ImportError:
    sys.stderr.write(
            'mwclient or ConfigParser not installed; install perhaps via pip.\n')
    raise


from_cmdline = False
try:
    __file__
    from_cmdline = True
except NameError:
    pass


if not from_cmdline:
    import vim

VALID_PROTOCOLS = [ 'http', 'https' ]
config = ConfigParser.ConfigParser()
config.read(os.path.expanduser('~/.write.conf'))

# Utility.

def sq_escape(s):
    return s.replace("'", "''")


def fn_escape(s):
    return vim.eval("fnameescape('%s')" % sq_escape(s))


def input(prompt, text='', password=False):
    vim.command('call inputsave()')
    vim.command("let i = %s('%s', '%s')" % (('inputsecret' if password else 'input'),
        sq_escape(prompt), sq_escape(text)))
    vim.command('call inputrestore()')
    return vim.eval('i')


def var_exists(var):
    return bool(int(vim.eval("exists('%s')" % sq_escape(var))))


def get_from_config(var):
    if var_exists(var):
        return vim.eval(var)
    return None


def get_from_config_or_prompt(var, prompt, password=False, text=''):
    c = get_from_config(var)
    if c is not None:
        return c
    else:
        resp = input(prompt, text=text, password=password)
        vim.command("let %s = '%s'" % (var, sq_escape(resp)))
        return resp


def base_url():
    return get_from_config_or_prompt('g:mediawiki_editor_url',
            "Mediawiki URL, like 'en.wikipedia.org': ")


def site():
    if site.cached_site:
        return site.cached_site

    scheme = get_from_config('g:mediawiki_editor_uri_scheme')
    if scheme not in VALID_PROTOCOLS:
        scheme = 'https'

    s = mwclient.Site((scheme, base_url()),
                      path=get_from_config_or_prompt('g:mediawiki_editor_path',
                                                     'Mediawiki Script Path: ',
                                                     text='/w/'),
                                                     httpauth=(config.get('wiki', 'auth_user'),
                                                     config.get('wiki', 'auth_pass')))
    try:
        s.login(
                config.get('wiki', 'user'),
                config.get('wiki', 'pass'))
    except mwclient.errors.LoginError as e:
        sys.stderr.write('Error logging in: %s\n' % e)
        raise

    site.cached_site = s
    return s

site.cached_site = None


def infer_default(article_name):
    if not article_name:
        article_name = vim.current.buffer.vars.get('article_name')
    else:
        article_name = article_name[0]

    if not article_name:
        sys.stderr.write('No article specified.\n')

    return article_name


# Commands.


def mw_read(article_name):
    s = site()
    b = vim.current.buffer
    if b[:] and b[0] is not None:
        # Buffer has content so
        # create vsplit and use that buffer
        vim.command('vnew')
        b = vim.current.buffer
    b[:] = s.Pages[article_name].text().split("\n")
    b.name = article_name
    vim.command('set ft=mediawiki')
    vim.command("let b:article_name = '%s'" % sq_escape(article_name))

def mw_write(article_name):
    article_name = infer_default(article_name)

    s = site()
    page = s.Pages[article_name]
    summary = input('Edit summary: ')
    minor = get_from_config('g:mediawiki_editor_minor_edit')

    print ' '

    result = page.save("\n".join(vim.current.buffer[:]), summary=summary,
            minor=minor)
    if result['result']:
        print 'Successfully edited %s.' % result['title']
    else:
        sys.stderr.write('Failed to edit %s.\n' % article_name)


def mw_diff(article_name):
    article_name = infer_default(article_name)

    s = site()
    vim.command('diffthis')
    vim.command('leftabove vsplit %s' % fn_escape(article_name + ' - REMOTE'))
    vim.command('setlocal buftype=nofile bufhidden=delete nobuflisted')
    vim.command('set ft=mediawiki')
    vim.current.buffer[:] = s.Pages[article_name].text().split("\n")
    vim.command('diffthis')
    vim.command('set nomodifiable')


def mw_browse(article_name):
    article_name = infer_default(article_name)

    url = 'https://%s/wiki/%s' % (base_url(), article_name)
    if not var_exists('g:loaded_netrw'):
        vim.command('runtime! autoload/netrw.vim')

    if var_exists('*netrw#BrowseX'):
        vim.command("call netrw#BrowseX('%s', 0)" % sq_escape(url))
    else:
        vim.command("call netrw#NetrwBrowseX('%s', 0)" % sq_escape(url))
