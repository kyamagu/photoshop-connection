"""
Kevlar API wrappers.

https://github.com/adobe-photoshop/generator-core/wiki/Photoshop-Kevlar-API-Additions-for-Generator
"""
import json
from jinja2 import Environment, PackageLoader
import logging

logger = logging.getLogger(__name__)


class Kevlar(object):
    """Kevlar API wrappers."""
    _env = Environment(
        loader=PackageLoader('photoshop', 'api'), trim_blocks=True
    )

    def _execute(self, template_file, context):
        command = self._env.get_template(template_file).render(context)
        logger.debug(command)
        return self.execute(command)

    def get_document_thumbnail(
        self,
        document=None,
        max_width=2048,
        max_height=2048,
        format=1,
        placed_ids=None
    ):
        """
        :param document: optional document id, uses active doc if not specified.
        :param max_width: maximum width of thumbnail.
        :param max_height: maximum height of thumbnail.
        :param format: 1 is JPEG, 2 is pixmap (uncompressed w/ transparency).
        :param placed_ids: Photoshop 16.1 and later, optional. reference smart
            object(s) within the document series of "ID" from
            layer:smartObject:{} or "placedID" from "image:placed:[{}]".
        :return: JPEG bytes if `format` is 1, or
            :py:class:`~photoshop.protocol.Pixmap` if `format` is 2.
        """
        response = self._execute(
            'sendDocumentThumbnailToNetworkClient.js.j2', locals()
        )
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
        response = self._execute(
            'sendLayerThumbnailToNetworkClient.js.j2', locals()
        )
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
        """
        response = self._execute(
            'sendLayerShapeToNetworkClient.js.j2', locals()
        )
        if response.get('body'):
            return json.loads(response.get('body'))
        return None
