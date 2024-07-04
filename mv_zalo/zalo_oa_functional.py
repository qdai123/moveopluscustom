# -*- coding: utf-8 -*-
import json


def ZNS_GET_SAMPLE_DATA(sample_id, obj_model):
    # Check if field_id is set
    if not sample_id.field_id:
        return None

    # Get the raw value
    raw_value = obj_model[sample_id.field_id.name]

    # Handle None values gracefully
    if raw_value is None:
        return None

    # Define a mapping for field types to their processing logic
    type_format_mapping = {
        "date": lambda x: x.strftime("%d/%m/%Y"),
        "datetime": lambda x: x.strftime("%d/%m/%Y"),
        "float": str,
        "integer": str,
        "monetary": str,
        "many2one": lambda x: x.name,
    }

    # Get the specific formatter based on field type and sample type
    formatter = type_format_mapping.get(sample_id.field_id.ttype)

    # Apply formatting if applicable, else return the string representation
    return formatter(raw_value) if formatter else str(raw_value)


def ZNS_GET_PAYLOAD(phone, template_id, template_data, tracking_id):
    return {
        "phone": phone,
        "template_id": template_id,
        "template_data": json.loads(template_data),
        "tracking_id": tracking_id,
    }


def ZNS_GET_MESSAGE_TEMPLATE(zns_message_id, zns_quota, sent_time):
    return (
        '<p class="mb-0">Đã gửi tin nhắn ZNS</p>'
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


def ZNS_GENERATE_MESSAGE(data, sent_time):
    return ZNS_GET_MESSAGE_TEMPLATE(data.get("msg_id"), data.get("quota"), sent_time)
