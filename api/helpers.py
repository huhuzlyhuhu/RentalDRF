from functools import lru_cache

import jwt
from django.db.models import Q, Prefetch
from django_filters import filterset
from jwt import InvalidTokenError
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from common.models import Estate, HouseInfo, User, Role
from zufang.settings import SECRET_KEY


class CustomThrottle(SimpleRateThrottle):

    def get_cache_key(self, request, view):
        pass


class DefaultResponse(Response):
    """定义返回JSON数据的响应类"""

    def __init__(self, code=100000, message='操作成功',
                 data=None, status=None, template_name=None,
                 headers=None, exception=False, content_type=None):
        _data = {'code': code, 'message': message}
        if data:
            _data.update(data)
        super().__init__(_data, status, template_name,
                         headers, exception, content_type)


class LoginRequiredAuthentication(BaseAuthentication):
    """登录认证"""

    # 如果用户身份验证成功需要返回一个二元组(user, token)
    def authenticate(self, request):
        token = request.META.get('HTTP_TOKEN')
        if token:
            try:
                payload = jwt.decode(token, SECRET_KEY)
                user = User()
                user.userid = payload['data']['userid']
                user.is_authenticated = True
                return user, token
            except InvalidTokenError:
                raise AuthenticationFailed('无效的令牌或令牌已过期')
        raise AuthenticationFailed('请提供用户身份令牌')


class RbacPermission(BasePermission):
    """RBAC授权"""

    # 返回True表示有操作权限，返回False表示没有操作权限
    def has_permission(self, request, view):
        privs = get_privs_by_userid(request.user.userid)
        for priv in privs:
            if request.path.startswith(priv.url) and \
                    request.method == priv.method:
                return True
        return False


@lru_cache(maxsize=256)
def get_privs_by_userid(userid):
    user = User.objects.filter(userid=userid)\
        .prefetch_related(
            Prefetch(
                'roles',
                queryset=Role.objects.all().prefetch_related('privs'))
        ).first()
    return [priv for role in user.roles.all()
            for priv in role.privs.all()]


class CustomPagePagination(PageNumberPagination):
    """自定义页码分页类"""
    page_size_query_param = 'size'
    max_page_size = 50


class AgentCursorPagination(CursorPagination):
    """经理人游标分页类"""
    page_size_query_param = 'size'
    max_page_size = 50
    ordering = '-agentid'


class EstateFilterSet(filterset.FilterSet):
    """自定义楼盘筛选器"""
    name = filterset.CharFilter(lookup_expr='startswith')
    minhot = filterset.NumberFilter(field_name='hot', lookup_expr='gte')
    maxhot = filterset.NumberFilter(field_name='hot', lookup_expr='lte')
    dist = filterset.NumberFilter(field_name='district')

    class Meta:
        model = Estate
        fields = ('name', 'minhot', 'maxhot', 'dist')


class HouseInfoFilterSet(filterset.FilterSet):
    """自定义房源筛选器"""
    title = filterset.CharFilter(lookup_expr='contains')
    minprice = filterset.NumberFilter(field_name='price', lookup_expr='gte')
    maxprice = filterset.NumberFilter(field_name='price', lookup_expr='lte')
    minarea = filterset.NumberFilter(field_name='area', lookup_expr='gte')
    maxarea = filterset.NumberFilter(field_name='area', lookup_expr='lte')
    district = filterset.NumberFilter(method='filter_by_district')

    @staticmethod
    def filter_by_district(queryset, name, value):
        return queryset.filter(Q(district_level2=value) |
                               Q(district_level3=value))

    class Meta:
        model = HouseInfo
        fields = ('title', 'minprice', 'maxprice', 'minarea', 'maxarea', 'type', 'district')
