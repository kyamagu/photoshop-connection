var idNS = stringIDToTypeID("sendDocumentThumbnailToNetworkClient");
var desc1 = new ActionDescriptor();
{% if document %}
desc1.putInteger(stringIDToTypeID("documentID"), {{document}});
{% endif %}
desc1.putInteger(stringIDToTypeID("width"), {{max_width}});
desc1.putInteger(stringIDToTypeID("height"), {{max_height}});
desc1.putInteger(stringIDToTypeID("format"), {{format}});
{% if placed_ids %}
var placedList = new ActionList();
    {% for placed_id in placed_ids %}
placedList.putString("{{placed_id}}");
    {% endfor %}
desc1.putList(stringIDToTypeID("placedID"), placedList);
{% endif %}
executeAction(idNS, desc1, DialogModes.NO);
