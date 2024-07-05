# -*- coding: utf-8 -*-
import json
import logging
import pprint
import socket

import requests
from odoo.addons.biz_zalo_common.models.common import NAME_API

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

NAME_API = dict(NAME_API)


class ZALOLogRequest(models.Model):
    _inherit = "zalo.log.request"

    # /// ZALO ZNS (HANDLERS) ///

    def zns_prepare_request_data(self, api_url, method, **kwargs):
        """Prepare request data including headers and payload."""
        request_data = {
            "url": api_url,
            "method": method,
            "headers": json.loads(kwargs.get("headers", "{}")),
            "params": json.loads(kwargs.get("params", "{}")),
            "payload": kwargs.get("payload"),
        }
        return request_data

    def zns_log_request_details(self, request_data):
        """Log the details of the HTTP request."""
        _logger.info(
            "Preparing to send request to ZALO API",
            extra={
                "URL": request_data["url"],
                "Method": request_data["method"],
                "Headers": request_data["headers"],
                "Params": request_data["params"],
                "Payload": request_data["payload"],
            },
        )

    def zns_execute_request(self, request_data):
        """Execute the HTTP request and return the response."""
        try:
            response = requests.request(
                request_data["method"],
                request_data["url"],
                params=request_data["params"],
                data=(
                    request_data["payload"].encode("utf-8")
                    if isinstance(request_data["payload"], str)
                    else request_data["payload"]
                ),
                headers=request_data["headers"],
            )
            _logger.debug(f"Response: {response.text}")
            return response
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
        ) as error:
            _logger.error(f"A network error occurred: {error}")
            raise UserError(f"A network error caused the failure of the job: {error}")
        except Exception as error:
            _logger.error(f"An unexpected error occurred: {error}")
            raise UserError(f"An unexpected error occurred: {error}")

    @api.model
    def zns_do_execute(self, api_url, method="GET", is_check=False, **kwargs):
        # Prepare the request data
        request_data = self.zns_prepare_request_data(api_url, method, **kwargs)
        self.zns_log_request_details(request_data)

        # Execute the request
        response = self.zns_execute_request(request_data)

        if is_check:
            # If is_check is True, return the raw response
            return response

        # Process the response based on your application's needs
        try:
            response_data = response.json()
            # Example of processing JSON response
            if response.status_code == 200:
                _logger.info("Successful request.")
                return {"success": True, "data": response_data}
            else:
                _logger.warning(f"Request failed with status: {response.status_code}")
                return {
                    "success": False,
                    "error": response_data.get("error", "Unknown error"),
                }
        except ValueError:
            # Handle non-JSON responses or other exceptions
            _logger.error("Failed to parse response as JSON.")
            raise UserError("Invalid response format received.")

    # /// ZALO ZNS (OVERRIDE) ///

    @api.model
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
