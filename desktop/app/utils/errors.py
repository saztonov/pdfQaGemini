"""Custom exceptions"""


class AppError(Exception):
    """Base application error"""
    pass


class ServiceError(AppError):
    """Service layer error"""
    pass


class CacheError(AppError):
    """Cache operation error"""
    pass
