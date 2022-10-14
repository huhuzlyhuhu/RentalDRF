import io
import random
from urllib.parse import quote

import xlwt
from django.db.models import Avg
from django.http import HttpResponse
from rest_framework.decorators import api_view

from api.helpers import DefaultResponse
from backend.models import Emp, Dept


@api_view(('GET', ))
def get_bar_data(request):
    queryset = Emp.objects.values('dept__name').annotate(avgsal=Avg('sal'))
    names, sals = [], []
    for result in queryset:
        names.append(result['dept__name'])
        sals.append('%.2f' % float(result['avgsal']))
    return DefaultResponse(data={
        'names': names,
        'sals': [
            sals,
            ['%.2f' % (random.randint(-1000, 1000) + float(sal)) for sal in sals],
            ['%.2f' % (random.randint(-1000, 1000) + float(sal)) for sal in sals],
            ['%.2f' % (random.randint(-1000, 1000) + float(sal)) for sal in sals],
        ]
    })


def export_excel(request):
    wb = xlwt.Workbook()
    sheet = wb.add_sheet('员工信息表')
    titles = ('编号', '姓名', '职位', '主管', '工资', '部门')
    for col, title in enumerate(titles):
        sheet.write(0, col, title)
    queryset = Emp.objects.all().defer('comm')
    props = ('no', 'name', 'job', 'mgr', 'sal', 'dept')
    for row, emp in enumerate(queryset):
        for col, prop in enumerate(props):
            value = getattr(emp, prop, '')
            if isinstance(value, (Dept, Emp)):
                value = value.name
            sheet.write(row + 1, col, value)
    buffer = io.BytesIO()
    wb.save(buffer)
    resp = HttpResponse(buffer.getvalue(), content_type='application/vnd.msexecl')
    filename = '员工信息表.xls'
    resp['content-disposition'] = f'attachment; filename="{quote(filename)}"'
    return resp
