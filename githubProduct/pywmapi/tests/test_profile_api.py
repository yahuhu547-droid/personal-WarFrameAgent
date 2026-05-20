import pytest

from pywmapi.auth.api import signin
from pywmapi.common import *
from pywmapi.profile import *
from tests.test_auth_api import get_test_signin_dict


def test_get_profile_by_username():
    get_profile_by_username("megan")


@pytest.mark.skip("No third-party support for sign-in in API")
def test_get_current_user():
    d = get_test_signin_dict()
    sess = signin(**d)
    get_current_user(sess)
