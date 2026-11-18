from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import BaseModel


class BaseModelFactory[T: BaseModel](ModelFactory[T]):
    __is_base_factory__ = True
    __check_model__ = True
