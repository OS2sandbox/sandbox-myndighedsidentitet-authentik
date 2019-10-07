import time

from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils.cache import patch_vary_headers
from django.utils.http import cookie_date
from structlog import get_logger

from passbook.factors.view import AuthenticationView

LOGGER = get_logger()

class SessionHostDomainMiddleware(SessionMiddleware):

    def process_request(self, request):
        session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
        request.session = self.SessionStore(session_key)

    def process_response(self, request, response):
        """
        If request.session was modified, or if the configuration is to save the
        session every time, save the changes and set a session cookie.
        """
        try:
            accessed = request.session.accessed
            modified = request.session.modified
        except AttributeError:
            pass
        else:
            if accessed:
                patch_vary_headers(response, ('Cookie',))
            if modified or settings.SESSION_SAVE_EVERY_REQUEST:
                if request.session.get_expire_at_browser_close():
                    max_age = None
                    expires = None
                else:
                    max_age = request.session.get_expiry_age()
                    expires_time = time.time() + max_age
                    expires = cookie_date(expires_time)
                # Save the session data and refresh the client cookie.
                # Skip session save for 500 responses, refs #3881.
                if response.status_code != 500:
                    request.session.save()
                    hosts = [request.get_host().split(':')[0]]
                    if AuthenticationView.SESSION_FORCE_COOKIE_HOSTNAME in request.session:
                        hosts.append(request.session[AuthenticationView.SESSION_FORCE_COOKIE_HOSTNAME])
                    LOGGER.debug("Setting hosts for session", hosts=hosts)
                    for host in hosts:
                        response.set_cookie(settings.SESSION_COOKIE_NAME,
                                            request.session.session_key, max_age=max_age,
                                            expires=expires, domain=host,
                                            path=settings.SESSION_COOKIE_PATH,
                                            secure=settings.SESSION_COOKIE_SECURE or None,
                                            httponly=settings.SESSION_COOKIE_HTTPONLY or None)
        return response
