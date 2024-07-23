# -*- coding: utf-8 -*-
import logging
import re

from odoo.addons.biz_zalo_common.models.common import CODE_ERROR_ZNS

# from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DATE_FORMAT
# from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DATETIME_FORMAT

_logger = logging.getLogger(__name__)

CODE_ERROR_ZNS = dict(CODE_ERROR_ZNS)

VIETNAM_DATE_FORMAT = "%d/%m/%Y"
VIETNAM_DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"


# ||| ==== ZALO Notification Service - ZNS ==== |||


def ZNS_GET_DATA_BY_TEMPLATE(record_id, model):
    """
    Fetches and formats data from a model based on the template configuration.

    :param record_id: The template record containing field and type information.
    :param model: The model instance from which data is to be fetched.
    :return: Formatted data based on the template configuration, or None if an error occurs.
    """
    if not record_id or not record_id.field_id:
        _logger.error(
            f"[zns_get_data_by_template] Invalid input or Field ID not found on Record: {record_id}"
        )
        return None

    zns_data_type = record_id.type
    zns_data_field_name = record_id.field_id.name
    zns_data_field_type = record_id.field_id.ttype

    _logger.debug(
        f"[zns_get_data_by_template] Processing {zns_data_field_name} ({zns_data_field_type}) as {zns_data_type}"
    )

    # Ensure the model has the specified field
    if zns_data_field_name not in model:
        _logger.error(
            f"[zns_get_data_by_template] Field {zns_data_field_name} not found in model."
        )
        return None

    raw_value = model[zns_data_field_name]

    # Apply formatting based on the field type and data type
    return zns_mapping_data_by_type(zns_data_type, raw_value)


def ZNS_GET_PAYLOAD(phone, template_id, template_data, tracking_id):
    return {
        "phone": phone,
        "template_id": template_id,
        "template_data": template_data,
        "tracking_id": tracking_id,
    }


def ZNS_GENERATE_MESSAGE(data, sent_time):
    return ZNS_GET_MESSAGE_TEMPLATE(data.get("msg_id"), data.get("quota"), sent_time)


def ZNS_GET_MESSAGE_TEMPLATE(zns_message_id, zns_quota, sent_time):
    return (
        """<p class="mb-0">Đã gửi tin nhắn ZNS</p>"""
        + """
            <ul class="o_Message_trackingValues mb-0 ps-4">
                <li>
                    <div class="o_TrackingValue d-flex align-items-center flex-wrap mb-1" role="group">
                        <span class="o_TrackingValue_oldValue me-1 px-1 text-muted fw-bold">ID thông báo ZNS: </span>
                        <span class="o_TrackingValue_newValue me-1 fw-bold text-info">{zns_message_id}</span>
                    </div>
                </li>
                <li>
                    <div class="o_TrackingValue d-flex align-items-center flex-wrap mb-1" role="group">
                        <span class="o_TrackingValue_oldValue me-1 px-1 text-muted fw-bold">Thời gian gửi thông báo ZNS: </span>
                        <span class="o_TrackingValue_newValue me-1 fw-bold text-info">{sent_time}</span>
                    </div>
                </li>
                <li>
                    <div class="o_TrackingValue d-flex align-items-center flex-wrap mb-1" role="group">
                        <span class="o_TrackingValue_oldValue me-1 px-1 text-muted fw-bold">Thông tin quota thông báo ZNS của OA: </span>
                        <span class="o_TrackingValue_newValue me-1 fw-bold text-info">{zns_quota}</span>
                    </div>
                </li>
            </ul>
        """.format(
            zns_message_id=zns_message_id, sent_time=sent_time, zns_quota=zns_quota
        )
    )


# ||| ==== HELPER FUNCTIONS ==== |||


def zns_mapping_data_by_type(zns_data_type, raw_value):
    if raw_value is None:
        return None

    if zns_data_type == "DATE":
        return raw_value.strftime(VIETNAM_DATE_FORMAT)
    elif zns_data_type == "DATETIME":
        return raw_value.strftime(VIETNAM_DATETIME_FORMAT)
    elif zns_data_type == "NUMBER":
        return str(raw_value)
    elif zns_data_type == "CURRENCY":
        # Assuming raw_value is a float, round it before converting to int to avoid truncation
        return int(round(raw_value))
    elif zns_data_type == "STRING":
        # Check if raw_value has a 'name' attribute, common for 'Many2one' fields in Odoo
        return raw_value.name if hasattr(raw_value, "name") else str(raw_value)
    else:
        return str(raw_value)


def zns_convert_valid_phonenumber(phonenumber):
    """
    Convert a given phone number to a valid format by:
    1. Removing any whitespace.
    2. Replacing the leading '0' with '84' (Vietnam's country code).

    Args:
        phonenumber (str): The input phone number.

    Returns:
        str: The formatted phone number or None if the input is invalid.
    """
    if not isinstance(phonenumber, str):
        raise ValueError("Input must be a string")

    # Remove all whitespace characters
    valid_phonenumber = re.sub(r"\s+", "", phonenumber, flags=re.UNICODE)

    # Check if the phone number is not empty and starts with '0'
    if valid_phonenumber and valid_phonenumber[0] == "0":
        # Replace the leading '0' with '84'
        return "84" + valid_phonenumber[1:]

    # Return the phone number as-is if no changes are needed
    return valid_phonenumber if valid_phonenumber else None
