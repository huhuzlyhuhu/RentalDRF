import random


class MasterSlaveRouter:

    @staticmethod
    def db_for_read(model, **hints):
        if model._meta.app_label == 'hrs':
            return 'backend'
        return random.choice(('slave1', 'slave2', 'slave3'))

    @staticmethod
    def db_for_write(model, **hints):
        if model._meta.app_label == 'hrs':
            return 'backend'
        return 'default'

    @staticmethod
    def allow_relation(obj1, obj2, **hints):
        return None

    @staticmethod
    def allow_migrate(db, app_label, model_name=None, **hints):
        return True
