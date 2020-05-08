"""
Kevlar API wrappers.

https://github.com/adobe-photoshop/generator-core/wiki/Photoshop-Kevlar-API-Additions-for-Generator
"""
import json
import threading
from enum import Enum
from photoshop.protocol import ContentType
import logging

logger = logging.getLogger(__name__)


class Event(str, Enum):
    """
    List of events in :py:meth:`~photoshop.PhotoshopConnection.subscribe`.

    See `Kevlar API`_.

    .. _Kevlar API: https://github.com/adobe-photoshop/generator-core/wiki/Photoshop-Kevlar-API-Additions-for-Generator).
    """
    imageChanged = 'imageChanged'
    generatorMenuChanged = 'generatorMenuChanged'
    generatorDocActivated = 'generatorDocActivated'
    foregroundColorChanged = 'foregroundColorChanged'
    backgroundColorChanged = 'backgroundColorChanged'
    currentDocumentChanged = 'currentDocumentChanged'
    activeViewChanged = 'activeViewChanged'
    newDocumentViewCreated = 'newDocumentViewCreated'
    closedDocument = 'closedDocument'
    documentChanged = 'documentChanged'
    colorSettingsChanged = 'colorSettingsChanged'
    keyboardShortcutsChanged = 'keyboardShortcutsChanged'
    quickMaskStateChanged = 'quickMaskStateChanged'
    toolChanged = 'toolChanged'
    workspaceChanged = 'workspaceChanged'
    Asrt = 'Asrt'
    idle = 'idle'


def listen_event(self, event, callback):
    event = Event(event)
    begin = self._render('networkEventSubscribe.js.j2', dict(event=event))
    with self._transaction() as txn:
        txn.send(ContentType.SCRIPT_SHARED, begin.encode('utf-8'))
        try:
            while True:
                response = txn.receive()
                data = response.get('body')
                if data == b'[ActionDescriptor]':
                    continue
                data = data.split(b'\r', 1)
                assert data[0].decode('utf-8') == event
                result = callback(self, data[1] if len(data) else None)
                if result:
                    break
        except Exception as e:
            if not isinstance(e, OSError):
                logger.error('%s' % e)
            return

    end = self._render('networkEventUnsubscribe.js.j2', dict(event=event))
    with self._transaction() as txn:
        txn.send(ContentType.SCRIPT_SHARED, end.encode('utf-8'))
        assert txn.receive().get('body') == b'[ActionDescriptor]'


class Kevlar(object):
    """Kevlar API wrappers."""
    def subscribe(self, event, callback, block=False, **kwargs):
        """
        Subscribe to changes, sends any relevant change info back on subscribing
        socket.

        :param event: Event name, one of :py:class:`~photoshop.Event`.
        :param callback: Callable that takes two arguments:

            - `conn`: :py:class:`~photoshop.PhotoshopConnection` instance.
            - `data`: `bytes` data returned from Photoshop on this event. The
              actual data format varies by event type.

              Return value of `callback` signals termination of the current
              subscription. If `callback` returns True, subscription stops.

        :param block: Block until subscription finishes. default `False`.

        Example::

            import json
            import time

            def handler(conn, data):
                print(json.loads(data.decode('utf-8')))
                return True  # This terminates subscription

            with PhotoshopConnection() as conn:
                conn.subscribe('imageChanged', handler)
                conn.execute('documents.add()')
                time.sleep(5)
        """
        assert callable(callback)
        thread = threading.Thread(
            target=listen_event, args=(self, event, callback), daemon=True
        )
        self.subscribers.append(thread)
        thread.start()
        if block:
            thread.join()

    def get_document_thumbnail(
        self,
        document=None,
        max_width=2048,
        max_height=2048,
        format=1,
        placed_ids=None
    ):
        """
        Send a thumbnail of a document's composite.

        :param document: optional document id, uses active doc if not specified.
        :param max_width: maximum width of thumbnail.
        :param max_height: maximum height of thumbnail.
        :param format: 1 is JPEG, 2 is pixmap (uncompressed w/ transparency).
        :param placed_ids: Photoshop 16.1 and later, optional. reference smart
            object(s) within the document series of "ID" from
            layer:smartObject:{} or "placedID" from "image:placed:[{}]".
        :return: JPEG bytes if `format` is 1, or
            :py:class:`~photoshop.protocol.Pixmap` if `format` is 2.
        :raise RuntimeError: if error happens in remote.
        """
        script = self._render(
            'sendDocumentThumbnailToNetworkClient.js.j2', locals()
        )
        response = self.execute(script, receive_output=True)
        assert response['content_type'] == ContentType.IMAGE
        return response.get('body', {}).get('data')

    def get_layer_thumbnail(
        self,
        document=None,
        max_width=2048,
        max_height=2048,
        convert_rgb_profile=True,
        icc_profile=None,
        interpolation=None,
        transform=None,
        layer=None,
        layer_settings=None,
        image_settings=None,
        include_layers=None,
        clip_bounds=None,
        bounds=False,
        bounds_only=False,
        thread=None,
        layer_comp_id=None,
        layer_comp_index=None,
        dither=True,
        color_dither=True
    ):
        """
        Send a thumbnail of layer composite, or a range of layers, with optional
        settings/transform applied.

        :param document: optional document id, uses active doc if not specified.
        :param max_width: maximum width of thumbnail.
        :param max_height: maximum height of thumbnail.
        :param placed_ids: Photoshop 16.1 and later, optional. reference smart
            object(s) within the document series of "ID" from
            layer:smartObject:{} or "placedID" from "image:placed:[{}]".
        :param convert_rgb_profile: if True, the thumbnail is converted to the
            working RGB space in "Color Settings...".
        :param icc_profile: optional, Photoshop 16.1, and later.
            convert to profile with this name, e.g. srgb is "sRGB IEC61966-2.1"
        :param interpolation: interpolation method to use for any downscaling
            necessary to fit into requested "width"/"height".
            supported interpolation types (from image size dialog/action):

            - "nearestNeighbor"
            - "bilinear"
            - "bicubic"
            - "bicubicSmoother"
            - "bicubicSharper"
            - "bicubicAutomatic"
            - "preserveDetailsUpscale"
            - "automaticInterpolation"

            default is "bicubicSharper".
        :param transform: scale/transform layers by this before building
            thumbnails (scales original source data, such as smart obj/vectors).
            if this is specified, the thumbnail is built on a worker thread in
            Photoshop.

            Example::

                transform = {
                    'scale_x': 100.0,
                    'scale_y': 100.0,
                    'interpolation': 'bicubicSharper',
                    'dumb_scaling': True
                }

            - `scale_x`: percent, 100.0 == 1x
            - `scale_y`: percent, 100.0 == 1x
            - `interpolation`: Optional, similar to interpolation above,
              but this is just used for the transform step (not the thumbnail),
              it defaults to Photoshop's "Image Interpolation" preference.
            - `dumb_scaling`: For PS >= 14.2. Make smart shapes scale like
              non-smart shapes (round rect corners will scale), default is
              False.
        :param layer: `None` for currently selected layers in photoshop, or
            specify one of the following:
            - integer ID of a single layer, e.g. `0`.
            - (`first`, `last`) tuple of layer IDs, e.g., (1, 6).
        :param document: optional document id, uses active doc if not specified
        :param layer_settings: Action list to modify the layer before the
            thumbnail is retrieved. This option is available when `layer` param
            is specified by tuple range. The argument should be list of dict
            with the following keys:

            - `enabled`: make the layer visible/invisible.
            - `blendOptions`: blending settings to use.
            - `layerEffects`: fx settings to use.
            - `offset`: integer offset of layer in dict.
            - `vectorMask`: vector mask to apply in dict.
            - `FXRefPoint`: effect reference point.

            Example::

                [
                    {
                        'enabled': True,
                        'blendOptions': [],
                        'layerEffects': [],
                        'offset': {
                            'horizontal': 0,
                            'vertical': 0
                        },
                        'vectorMask': {
                            'enabled': False,
                            'offset': {
                            }
                            'invert': False,
                        },
                        'FXRefPoint': {
                            'horizontal': 0,
                            'vertical': 0
                        }
                    }
                ]

        :param image_settings:
        :param include_layers: include additional layers to the requested layer.
            dict with one or more of the following keys.

            - `adjustors`: adjustors above the layer, default is `visible`.
            - `ancestors`: enclosing groups (includes group blending, fx, masks
              ), default is `all`. `visible` and `all` incorporate any blending
              parameters/masks of the ancestor groups. `visible` returns an
              empty thumbnail for any layer inside an invisible group. `none`
              substitutes default groups for any groups around the layer.
            - `children`: if layer is a group (includes group blending, fx,
              masks), default is `visible`.
            - `clipbase`: clip base if layer is clipped. The clip base is a
              layer that a clipped layer is clipped to, default is `all`.
            - `clipped`: clipped layers if layer is clip base, default is
              `visible`.

            Values are one of `'all'`, `'none'`, or `'visible'`.

            - `all`: include all layers of this type (force them visible).
            - `none`: include no layers of this type.
            - `visible`: include visible layers of this type.

            Example::

                {
                    'adjustors': 'none',
                    'children': 'all',
                }

        :param clip_bounds: clip the layer thumbnail to the document canvas
            bounds if specified. Can specify `True` to bound to document size,
            or specify tuple of (`top`, `left`, `right`, `bottom`).
        :param bounds: return the thumbnail bounds as JSON on same transaction.
            (default is False).
        :param bounds_only: Just return the thumbnail bounds as JSON on same
            transaction. (no thumbnail data) (default is false).
        :param thread: build the thumbnail on a thread.  By default, the
            thumbnail is threaded if there is a "transform", otherwise it is
            done on the main thread unless a user event occurs, then it is
            cancelled, and restarted on a thread `thread` can be used to
            override the default (either force the thumb to be started on the
            main thread or a background thread) it may help performance if you
            know that the thumbnail is either quick (best done on main thread)
            or slow (best done on background) there is a slight
            memory/performance penalty for threading in that the layer data
            must be copied before it is threaded.
        :param layer_comp_id: layer comp id to use (this comp is temporarily
            applied before getting thumbnail).
        :param layer_comp_index: layer comp index to use (this comp is
            temporarily applied before getting thumbnail).
        :param dither: 15.0 and later. If
            1) `dither` is true
            2) and either `color_dither` is false, or `dither` is
            checked in the global color settings (Color Settings... in
            Photoshop)
            3) and any color/depth conversion would be “lossy” (16 to 8 bit,
            CMYK to RGB, etc),
            then dithering will occur, otherwise there will be no dithering.
        :param color_dither: see above.
        :return: :py:class:`~photoshop.protocol.Pixmap` or `None`.
        :raise RuntimeError: if error happens in remote.

        .. note:: "interpolation", "transform", "bounds", "boundsOnly", and
            "thread" are supported in background-only (layer-less) documents
            but only in version 15.0 and later.  "layerID" should be 0 in that
            case. The other layer-related settings are ignored as there are no
            layers.

        .. warning:: if `layer` tuple range includes a group layer, it must
            include the corresponding hidden "divider" layer at the bottom of
            the group (and vice-versa). The range can also just include layers
            inside a group with no group layers at all.
        """
        script = self._render(
            'sendLayerThumbnailToNetworkClient.js.j2', locals()
        )
        response = self.execute(script, receive_output=True)
        assert response['content_type'] == ContentType.IMAGE
        return response.get('body', {}).get('data')

    def get_layer_shape(
        self, document=None, layer=None, version='1.0.0', placed_ids=None
    ):
        """
        Return path/fill/strokeStyle for a shape layer(s).

        :param document: optional document id, uses active doc if not specified.
        :param placed_ids: Photoshop 16.1 and later, optional. reference smart
            object(s) within the document series of "ID" from
            layer:smartObject:{} or "placedID" from "image:placed:[{}]".
        :param layer: `None` for currently selected layers in photoshop, or
            specify one of the following:
            - integer ID of a single layer, e.g. `0`.
            - (`first`, `last`) tuple of layer IDs, e.g., (1, 6).
        :param version: format version. Valid versions are 1.0.0 in 14.1, and
            1.0, 1.0.0, 1.1, or 1.1.0 in Photoshop 14.2
        :return: `dict` of the following schema, or `None` if no valid layer is
            specified.

        Schema:

        .. code-block:: none

            {"path":
                {"pathComponents": // arrays of paths to be filled and boolean operators
                    [{"shapeOperation": ("intersect"/"add"/"subtract"/"xor")
                    "subpathListKey":[  //list of subpath objects that make up the component
                        {"closedSubpath":true, // (if subpath is closed)
                         "points": [{" // array of knot objects (anchor and control points)
                            anchor:[x,y]        //point on path
                            forward:[x1,y1]     //forward bezier control
                            backward:[x2,y2]    //backward bezier control
                            },  //next knot...
                            ...]
                    "origin":{"origin": ("ellipse"/"rect"/"roundedrect"/"line"/"unknown")
                    "radii":  [r1,r2,r3,r4], //radii for rounded rect if any
                "bounds":["top":top,"left":left,"right":right,"bottom":bottom], //bounds of entire path
                "defaultFill":true/false}, //whether path starts out filled or not
            "fill":
                {"color":{"red":red,"green":green,"blue":blue},"class":"solidColorLayer"}
                //or
                {"gradient":{(gradient object)},"class":"gradientLayer"}
                //or
                {"pattern":{(pattern object)},"class":"patternLayer"}
            "strokeStyle":
                {(strokeStyle object)}
            }

        Example::

            {"path":{"pathComponents":
                    [{"shapeOperation":"add",
                      "subpathListKey":[
                        {"closedSubpath":true,
                         "points": [{"anchor":[234.5,36],"forward":[307.125,36],"backward":[161.875,36]},
                            {"anchor":[366,167],"forward":[366,239.349],"backward":[366,94.651]},
                            {"anchor":[234.5,298],"forward":[161.875,298],"backward":[307.125,298]},
                            {"anchor":[103,167],"forward":[103,94.651],"backward":[103,239.349]}]
                        }],
                       "origin":{"origin":"ellipse","bounds":[35,102,299,367]}
                    }],
                "bounds":[35,102,299,367],
                "defaultFill":false},
            "fill":{"color":{"red":0,"green":0,"blue":0},"class":"solidColorLayer"}
            }

        :raise RuntimeError: if error happens in remote.
        """
        script = self._render('sendLayerShapeToNetworkClient.js.j2', locals())
        response = self.execute(script, receive_output=True)
        assert response['content_type'] == ContentType.SCRIPT
        return json.loads(response.get('body', b'{}').decode('utf-8'))

    def get_document_info(
        self,
        version=None,
        document=None,
        placed_ids=None,
        layer=None,
        expand_smart_objects=False,
        get_text_styles=False,
        get_full_text_styles=False,
        get_default_layer_effect=False,
        get_comp_layer_settings=False,
        get_path_data=False,
        image_info=None,
        comp_info=None,
        layer_info=True,
        include_ancestors=True
    ):
        """
        Return complete document info in JSON format.

        :param version: optional requested version (you always get the current
            version back, but this does a sanity check, and errors on an
            incompatible version). Example: '1.4.0'.
        :param document: optional document id, uses active doc if not specified.
        :param placed_ids: Photoshop 16.1 and later, optional. reference smart
            object(s) within the document series of "ID" from
            layer:smartObject:{} or "placedID" from "image:placed:[{}]".
        :param layer: `None` for all layers in photoshop, or
            specify one of the following:
            - integer ID of a single layer, e.g. `0`.
            - (`first`, `last`) tuple of layer IDs, e.g., (1, 6).
            - `'selected'` for currently selected layers.
        :param expand_smart_objects: default is false, recursively get doc info
            for any smart objects. can be slow.
        :param get_text_styles: default is false, return more detailed text
            info. can be slow.
        :param get_full_text_styles: default is false, return all text
            information (getTextStyles must also be true).
        :param get_default_layer_effect: default is false, return all layer fx
            even if they are disabled.
        :param get_comp_layer_settings: default is false, enumerate layer
            settings in layer comps.
        :param get_path_data: default is false, return path control points for
            shapes.
        :param image_info: return image-wide info (size, resolution etc.),
            default is `layer` != 'selected'.
        :param comp_info: return comp info in "comps" array, default is true,
            default is `layer` != 'selected'.
        :param layer_info: return layer info in "layers" array, default is true.
        :param include_ancestors: 16.1 and later, include surrounding layer
            groups if doing selected layers/range/single layer id. default is
            true. should only be used with single layers (otherwise grouping
            may not be accurate).
        :return: `dict`.
        :raise RuntimeError: if error happens in remote.
        """
        # TODO: Implement whichInfo option.
        script = self._render(
            'sendDocumentInfoToNetworkClient.js.j2', locals()
        )
        response = self.execute(script, receive_output=True)
        assert response['content_type'] == ContentType.SCRIPT
        return json.loads(response.get('body', b'{}').decode('utf-8'))

    def get_document_stream(
        self,
        document=None,
        placed_ids=None,
        placed_id=None,
        layer=None,
        position=None,
        size=None,
        path_only=None
    ):
        """
        Get the file info and file stream for a smart object.

        :param document: optional document id, uses active doc if not specified.
        :param placed_ids: Photoshop 16.1 and later, optional. reference smart
            object(s) within the document series of "ID" from
            layer:smartObject:{} or "placedID" from "image:placed:[{}]".
        :param placed_id: return file for smart object with this placed id ("ID"
            from layer:smartObject:{} or "placedID" from "image:placed:[{}]").
        :param layer: when integer ID of a single layer is specified, e.g. `0`,
            return file for smart object with this layer id. When `placed_id` is
            `None` and layer is also `None`, return placed smart object stream
            the selected layers
        :param position: offset into file (defaults to 0).
        :param size: number of bytes to return (defaults to all bytes).
        :param path_only: instead of returning the file stream back over the
            wire, write it to a file local to the server, and return the path as
            a string argument in the JSON part of the FileStream Reply.
        :return: `dict` with the following fields:

            - `mimeFormat`: mime string.
            - `position` : position of file data returned.
            - `size` : number of file bytes returned.
            - `fullSize` : total number of bytes in file.
            - `path` : string, server-local path to file if path was set to true
              in the request).
            - `data`: actual data in bytes. if `path` is True, this is empty.

        :raise RuntimeError: if error happens in remote.

        .. note:: The maximum size returned by PS is 2 GB, if you have a smart
            object bigger than 2 GB, you need to use the position/size format.
            To return chunks, or the path format to write it to a temp file.
            Document stream/attributes are returned as a FileStream Reply.
        """
        script = self._render(
            'sendDocumentStreamToNetworkClient.js.j2', locals()
        )
        response = self.execute(script, receive_output=True)
        assert response['content_type'] == ContentType.FILE_STREAM
        return response.get('body')
