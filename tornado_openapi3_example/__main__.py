import json
import os
import logging
import pathlib
import pkg_resources

import msgpack
from openapi_core import create_spec  # type: ignore
from openapi_core.exceptions import OpenAPIError  # type: ignore
from openapi_core.deserializing.exceptions import DeserializeError  # type: ignore
from openapi_core.schema.media_types.exceptions import (  # type: ignore
    InvalidContentType,
)
from openapi_core.templating.paths.exceptions import OperationNotFound  # type: ignore
from openapi_core.unmarshalling.schemas.exceptions import ValidateError  # type: ignore
from openapi_core.validation.exceptions import InvalidSecurity  # type: ignore
import tornado.ioloop
import tornado.web
from tornado_openapi3 import RequestValidator
import yaml


class OpenAPISpecHandler(tornado.web.RequestHandler):
    async def get(self) -> None:
        self.set_header("Content-Type", "application/x-yaml")
        return self.render("openapi.yaml")


class OpenAPIRequestHandler(tornado.web.RequestHandler):
    async def prepare(self) -> None:
        maybe_coro = super().prepare()
        if maybe_coro and asyncio.iscoroutine(maybe_coro):  # pragma: no cover
            await maybe_coro

        spec = create_spec(yaml.safe_load(self.render_string("openapi.yaml")))
        validator = RequestValidator(spec)
        result = validator.validate(self.request)
        try:
            result.raise_for_errors()
        except OperationNotFound:
            self.set_status(405)
            self.finish()
        except InvalidContentType:
            self.set_status(415)
            self.finish()
        except (DeserializeError, ValidateError):
            self.set_status(400)
            self.finish()
        except InvalidSecurity:
            self.set_status(401)
            self.finish()
        except OpenAPIError:
            raise
        self.validated = result


class LoginHandler(OpenAPIRequestHandler):
    async def post(self) -> None:
        self.set_header("Content-Type", "application/json")
        self.finish(
            json.dumps(
                {
                    "username": self.validated.body["username"],
                }
            )
        )


class NoteHandler(OpenAPIRequestHandler):
    async def get(self, identifier: str) -> None:
        self.set_header("Content-Type", "application/json")
        self.finish(
            json.dumps(
                {
                    "subject": "Shopping list",
                    "body": "\n".join(["- Dish soap", "- Potatoes", "- Milk"]),
                }
            )
        )


def make_app():
    pkg_root = pathlib.Path(pkg_resources.resource_filename(__package__, ""))
    return tornado.web.Application(
        [
            (r"/", tornado.web.RedirectHandler, {"url": "/static/index.html"}),
            (
                r"/static/(.*)",
                tornado.web.StaticFileHandler,
                {"path": pkg_root / "static", "default_filename": "index.html"},
            ),
            (f"/openapi.yaml", OpenAPISpecHandler),
            (r"/login", LoginHandler),
            (r"/notes/(?P<identifier>.+)", NoteHandler),
        ],
        debug=os.environ.get("DEBUG"),
        template_path=str(pkg_root / "templates"),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app = make_app()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
