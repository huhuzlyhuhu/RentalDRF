from django.db import models


class Dept(models.Model):
    no = models.IntegerField(primary_key=True, db_column='dno')
    name = models.CharField(max_length=10, db_column='dname')
    loc = models.CharField(max_length=20, db_column='dloc')

    class Meta:
        managed = False
        app_label = 'hrs'
        db_table = 'tb_dept'


class Emp(models.Model):
    no = models.IntegerField(primary_key=True, db_column='eno')
    name = models.CharField(max_length=20, db_column='ename')
    job = models.CharField(max_length=20)
    mgr = models.ForeignKey('self', models.DO_NOTHING, db_column='mgr', null=True)
    sal = models.IntegerField()
    comm = models.IntegerField(null=True)
    dept = models.ForeignKey(Dept, models.DO_NOTHING, db_column='dno')

    class Meta:
        managed = False
        app_label = 'hrs'
        db_table = 'tb_emp'
