# -*- coding: utf-8 -*-
import json
import logging
import pprint
import socket

import requests
from odoo.addons.biz_zalo_common.models.common import NAME_API

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

NAME_API = dict(NAME_API)


class ZALOLogRequest(models.Model):
    _inherit = "zalo.log.request"

    # /// ZALO ZNS (OVERRIDE) ///

    def do_execute(self, api_url, method="GET", is_check=False, **kwargs):
        value = {
            "url": api_url,
            "name": NAME_API.get(api_url, ""),
            "method": method,
            "user_id": self._uid,
        }
        if "headers" in kwargs and kwargs["headers"]:
            value["headers"] = kwargs["headers"]
        if "payload" in kwargs and kwargs["payload"]:
            value["payload"] = kwargs["payload"]
        if "params" in kwargs and kwargs["params"]:
            value["params"] = kwargs["params"]
        self_obj = self.sudo().create(value)
        data = json.loads(self_obj.payload) if not is_check else self_obj.payload

        try:
            _logger.info(
                "\n >>>>>>>>>> ZALO - BEGIN: event received <<<<<<<<<<<<<\n%s\n\n",
                pprint.pformat(
                    {
                        "URL": self_obj.url,
                        "headers": json.loads(self_obj.headers),
                        "method": self_obj.method,
                        "params": self_obj.params,
                        "data": data,
                    }
                ),
            )
            response = requests.request(
                self_obj.method,
                self_obj.url,
                params=json.loads(self_obj.params),
                data=data.encode("utf-8") if isinstance(data, str) else data,
                headers=json.loads(self_obj.headers),
            )
            _logger.debug(f"Response: {response.text}")
            _logger.info(">>>>>> ZALO - END: event received <<<<<<<<<<<<<")
        except (socket.gaierror, socket.error, socket.timeout) as error:
            raise UserError(
                _("A network error caused the failure of the job: %s", error)
            )
        except Exception as error:
            raise UserError(_(error))

        return self_obj.handle_response(response, is_check=is_check)
