# -*- coding: utf-8 -*-
"""
Configuration constants for the application.
"""

# 상수 정의
CONFIG_FILE = "config.json"
DEFAULT_CLIPPINGS_DIR = "clippings"
DEFAULT_ASSETS_DIR = "clippings/assets"
MAX_IMAGE_SIZE = 1200
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 네이버 로그인 쿠키 (멤버 공개 글 접근용)
# F12 > Application > Cookies에서 값 복사
NAVER_COOKIES = {
    'NID_AUT': 'CO3kGROeWBLY4e4HNfpuyIdTMKOfNCpvzC6CYXqPmneTCNHbWtsxF7RgtywZiyjc',
    'NID_SES': 'AAABrS+rqVa6npDAENYi3SRVaixfwQ1LRr3HXhJB+6+JdrIWSo7onDbvatwGb3EnA0SM5G9rT+ipZtkIVfzC1thgb+QyXY6e08CE/nDogE/e/SSHPbSBFQEsLCVnMpRliRML5k0FD7u+ZIOWM6bOW9JZ2DTLIDCq1vHv0RgijDCwFE/wZyLpBs2uqVGj0o/8/RIA9N56RsHRId6rwStc/Xbou7NWJmK0hYWryygZ0tajc5Cp39DC3W6ZttTS46v/8ciZDcC5k31YM7vdGX1sT9Nbu6juRCa9kTAwOWC4fcnPm0gavcDQjH0uyXNV3vbv3KJQDpem9X3vsSAeGekuk6lBipg6EDjNZZsHEDGKNMGx1CzYlmPQn4qTUXA7gmdlP9IdMObMuhKuJD6P5zxcNeep2lz/mbIbi25AuNkw+MrA8FCEZJn1FCbkRcboIyaxRqoCN9hj3Yx+x8QycubzNZsUn/FEtDFMSxL4NFIonmbU8SPS5RVtn57DEZGT2ooBOZdx3ODdkXfzdDXAsThA1NIwz3BKlLsAg6dE/DAOCbF7+JMQZ+mCAXry59E0NX0M6sox/g=='
}
