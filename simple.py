import json
import os
import time
import uuid
from copy import deepcopy
import dash
import dash_core_components as dcc
import dash_html_components as html
import requests
from dash.dependencies import Input, Output, State
from dotenv import load_dotenv, find_dotenv
from flask_caching import Cache

import dash_reusable_components as drc
from utils import STORAGE_PLACEHOLDER, GRAPH_PLACEHOLDER, \
    IMAGE_STRING_PLACEHOLDER
from utils import apply_filters, show_histogram, generate_lasso_mask, \
    apply_enhancements
from PIL import Image

DEBUG = True

app = dash.Dash(__name__)

#app.css.config.serve_locally = True
#app.script.config.serve_locally = True
server = app.server

im_pil0 = Image.open(os.path.join(os.getcwd(),'images','default.jpg'))
enc_format = 'jpeg'

cache_config = {
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': 'cache-directory',
}
# Caching
cache = Cache()
cache.init_app(app.server, config=cache_config)

plot_style = dict(
    plot_bgcolor="#191A1A",
    paper_bgcolor="#020202",
)

def serve_layout():
    # Generates a session ID
    session_id = str(uuid.uuid4())
    # App Layout
    return html.Div(
        style={'background-color': plot_style['plot_bgcolor']},
        children = [
        # Session ID
        html.Div(session_id, id='session-id', style={'display': 'none'}),

        # Banner display
        html.Div([
            html.H2(
                'Image Processing App',
                id='title'
            ),
        ],
            className="banner"
        ),

        # Body
        html.Div(className="container", 
            style={'background-color': plot_style['plot_bgcolor']},
            children=[
            html.Div(className='row', children=[
                html.Div(className='five columns', children=[
                    drc.Card([
                        dcc.Upload(
                            id='upload-image',
                            children=[
                                'Drag and Drop or ',
                                html.A('Select an Image')
                            ],
                            style={
                                'width': '100%',
                                'height': '50px',
                                'lineHeight': '50px',
                                'borderWidth': '1px',
                                'borderStyle': 'dashed',
                                'borderRadius': '5px',
                                'textAlign': 'center'
                            },
                            accept='image/*'
                        ),

                        drc.NamedInlineRadioItems(
                            name='Selection Mode',
                            short='selection-mode',
                            options=[
                                {'label': ' Rectangular', 'value': 'select'},
                                {'label': ' Lasso', 'value': 'lasso'}
                            ],
                            val='select'
                        ),

                        drc.NamedInlineRadioItems(
                            name='Image Display Format',
                            short='encoding-format',
                            options=[
                                {'label': ' JPEG', 'value': 'jpeg'},
                                {'label': ' PNG', 'value': 'png'}
                            ],
                            val='jpeg'
                        ),
                    ]),

                    drc.Card([
                        drc.CustomDropdown(
                            id='dropdown-filters',
                            options=[
                                {'label': 'Blur', 'value': 'blur'},
                                {'label': 'Contour', 'value': 'contour'},
                                {'label': 'Detail', 'value': 'detail'},
                                {'label': 'Enhance Edge', 'value': 'edge_enhance'},
                                {'label': 'Enhance Edge (More)', 'value': 'edge_enhance_more'},
                                {'label': 'Emboss', 'value': 'emboss'},
                                {'label': 'Find Edges', 'value': 'find_edges'},
                                {'label': 'Sharpen', 'value': 'sharpen'},
                                {'label': 'Smooth', 'value': 'smooth'},
                                {'label': 'Smooth (More)',
                                 'value': 'smooth_more'}
                            ],
                            searchable=False,
                            placeholder='Basic Filter...'
                        ),

                        drc.CustomDropdown(
                            id='dropdown-enhance',
                            options=[
                                {'label': 'Brightness', 'value': 'brightness'},
                                {'label': 'Color Balance', 'value': 'color'},
                                {'label': 'Contrast', 'value': 'contrast'},
                                {'label': 'Sharpness', 'value': 'sharpness'}
                            ],
                            searchable=False,
                            placeholder='Enhance...'
                        ),

                        html.Div(
                            id='div-enhancement-factor',
                            style={
                                'display': 'none',
                                'margin': '25px 5px 30px 0px'
                            },
                            children=[
                                f"Enhancement Factor:",
                                html.Div(
                                    style={'margin-left': '5px'},
                                    children=dcc.Slider(
                                        id='slider-enhancement-factor',
                                        min=0,
                                        max=2,
                                        step=0.1,
                                        value=1,
                                        updatemode='drag'
                                    )
                                )
                            ]
                        ),

                        html.Button(
                            'Run Operation',
                            id='button-run-operation',
                            style={'margin-right': '10px', 'margin-top': '5px'}
                        ),

                        html.Button(
                            'Undo',
                            id='button-undo',
                            style={'margin-top': '5px'}
                        )
                    ]),

                    dcc.Graph(id='graph-histogram-colors',
                              config={'displayModeBar': False},
                              style={'background-color': plot_style['plot_bgcolor']},
                            )
                ]),

                html.Div(
                    className='seven columns',
                    style={'float': 'right'},
                    children=[
                        # The Interactive Image Div contains the dcc Graph
                        # showing the image, as well as the hidden div storing
                        # the true image
                        html.Div(id='div-interactive-image', children=[
                            drc.InteractiveImagePIL(
                                image_id='interactive-image',
                                image=im_pil0,
                                enc_format=enc_format,
                                # display_mode='fixed',
                                # dragmode=dragmode,
                                verbose=DEBUG,
                                style=plot_style,
                            ),
                            html.Div(
                                id='div-storage',
                                children=STORAGE_PLACEHOLDER,
                                style={'display': 'none'}
                            )
                        ])
                    ]
                )
            ])
        ])
    ])


app.layout = serve_layout

# Helper functions for callbacks
def add_action_to_stack(action_stack,
                        operation,
                        operation_type,
                        selectedData):
    """
    Add new action to the action stack, in-place.
    :param action_stack: The stack of action that are applied to an image
    :param operation: The operation that is applied to the image
    :param operation_type: The type of the operation, which could be a filter,
    an enhancement, etc.
    :param selectedData: The JSON object that contains the zone selected by
    the user in which the operation is applied
    :return: None, appending is done in place
    """

    new_action = {
        'operation': operation,
        'type': operation_type,
        'selectedData': selectedData
    }

    action_stack.append(new_action)

def undo_last_action(n_clicks, storage):
    action_stack = storage['action_stack']

    if n_clicks is None:
        storage['undo_click_count'] = 0

    # If the stack isn't empty and the undo click count has changed
    elif len(action_stack) > 0 and n_clicks > storage['undo_click_count']:
        # Remove the last action on the stack
        action_stack.pop()

        # Update the undo click count
        storage['undo_click_count'] = n_clicks

    return storage

# Recursively retrieve the previous versions of the image by popping the
# action stack
@cache.memoize()
def apply_actions_on_image(session_id,
                           action_stack,
                           filename,
                           image_signature):
    action_stack = deepcopy(action_stack)

    # If we have arrived to the original image
    if len(action_stack) == 0:
        return im_pil0

    # Pop out the last action
    last_action = action_stack.pop()

    # Apply all the previous action_stack, and gets the image PIL
    im_pil = apply_actions_on_image(
        session_id,
        action_stack,
        filename,
        image_signature
    )
    im_size = im_pil.size

    # Apply the rest of the action_stack
    operation = last_action['operation']
    selectedData = last_action['selectedData']
    type = last_action['type']

    # Select using Lasso
    if selectedData and 'lassoPoints' in selectedData:
        selection_mode = 'lasso'
        selection_zone = generate_lasso_mask(im_pil, selectedData)
    # Select using rectangular box
    elif selectedData and 'range' in selectedData:
        selection_mode = 'select'
        lower, upper = map(int, selectedData['range']['y'])
        left, right = map(int, selectedData['range']['x'])
        # Adjust height difference
        height = im_size[1]
        upper = height - upper
        lower = height - lower
        selection_zone = (left, upper, right, lower)
    # Select the whole image
    else:
        selection_mode = 'select'
        selection_zone = (0, 0) + im_size

    # Apply the filters
    if type == 'filter':
        apply_filters(
            image=im_pil,
            zone=selection_zone,
            filter=operation,
            mode=selection_mode
        )
    elif type == 'enhance':
        enhancement = operation['enhancement']
        factor = operation['enhancement_factor']

        apply_enhancements(
            image=im_pil,
            zone=selection_zone,
            enhancement=enhancement,
            enhancement_factor=factor,
            mode=selection_mode
        )

    return im_pil


@app.callback(Output('interactive-image', 'figure'),
              [Input('radio-selection-mode', 'value')],
              [State('interactive-image', 'figure')])
def update_selection_mode(selection_mode, figure):
    if figure:
        figure['layout']['dragmode'] = selection_mode
    return figure


@app.callback(Output('graph-histogram-colors', 'figure'),
              [Input('interactive-image', 'figure')])
def update_histogram(figure):
    # Retrieve the image stored inside the figure
    enc_str = figure['layout']['images'][0]['source'].split(';base64,')[-1]
    # Creates the PIL Image object from the b64 png encoding
    im_pil = drc.b64_to_pil(string=enc_str)

    return show_histogram(im_pil)


@app.callback(Output('div-interactive-image', 'children'),
              [Input('upload-image', 'contents'),
               Input('button-undo', 'n_clicks'),
               Input('button-run-operation', 'n_clicks')],
              [State('interactive-image', 'selectedData'),
               State('dropdown-filters', 'value'),
               State('dropdown-enhance', 'value'),
               State('slider-enhancement-factor', 'value'),
               State('upload-image', 'filename'),
               State('radio-selection-mode', 'value'),
               State('radio-encoding-format', 'value'),
               State('div-storage', 'children'),
               State('session-id', 'children')])
def update_graph_interactive_image(content,
                                   undo_clicks,
                                   n_clicks,
                                   selectedData,
                                   filters,
                                   enhance,
                                   enhancement_factor,
                                   new_filename,
                                   dragmode,
                                   enc_format,
                                   storage,
                                   session_id):
    t_start = time.time()

    # Retrieve information saved in storage, which is a dict containing
    # information about the image and its action stack
    storage = json.loads(storage)
    filename = storage['filename']  # Filename is the name of the image file.
    image_signature = storage['image_signature']

    # Runs the undo function if the undo button was clicked. Storage stays
    # the same otherwise.
    storage = undo_last_action(undo_clicks, storage)

    # If a new file was uploaded (new file name changed)
    if new_filename and new_filename != filename:
        # Replace filename
        if DEBUG:
            print(filename, "replaced by", new_filename)

        # # Update the storage dict
        # storage['filename'] = new_filename

        # # Parse the string and convert to pil
        # string = content.split(';base64,')[-1]
        # im_pil = drc.b64_to_pil(string)

        # # Update the image signature, which is the first 200 b64 characters
        # # of the string encoding
        # storage['image_signature'] = string[:200]

        # # Posts the image string into the Bucketeer Storage (which is hosted
        # # on S3)
        # store_image_string(string, session_id)
        # if DEBUG:
        #     print(new_filename, "added to Bucketeer S3.")

        # # Resets the action stack
        # storage['action_stack'] = []

    # If an operation was applied (when the filename wasn't changed)
    else:
        # Add actions to the action stack (we have more than one if filters
        # and enhance are BOTH selected)
        if filters:
            type = 'filter'
            operation = filters
            add_action_to_stack(
                storage['action_stack'],
                operation,
                type,
                selectedData
            )

        if enhance:
            type = 'enhance'
            operation = {
                'enhancement': enhance,
                'enhancement_factor': enhancement_factor,
            }
            add_action_to_stack(
                storage['action_stack'],
                operation,
                type,
                selectedData
            )

        # Apply the required actions to the picture, using memoized function
        im_pil = apply_actions_on_image(
            session_id,
            storage['action_stack'],
            filename,
            image_signature
        )

    t_end = time.time()
    if DEBUG:
        print(f"Updated Image Storage in {t_end - t_start:.3f} sec")

    return [
        drc.InteractiveImagePIL(
            image_id='interactive-image',
            image=im_pil,
            enc_format=enc_format,
            display_mode='fixed',
            dragmode=dragmode,
            verbose=DEBUG
        ),

        html.Div(
            id='div-storage',
            children=json.dumps(storage),
            style={'display': 'none'}
        )
    ]



# Show/Hide Callbacks
@app.callback(Output('div-enhancement-factor', 'style'),
              [Input('dropdown-enhance', 'value')],
              [State('div-enhancement-factor', 'style')])
def show_slider_enhancement_factor(value, style):
    # If any enhancement is selected
    if value:
        style['display'] = 'block'
    else:
        style['display'] = 'none'

    return style

# Reset Callbacks
@app.callback(Output('dropdown-filters', 'value'),
              [Input('button-run-operation', 'n_clicks')])
def reset_dropdown_filters(_):
    return None

@app.callback(Output('dropdown-enhance', 'value'),
              [Input('button-run-operation', 'n_clicks')])
def reset_dropdown_enhance(_):
    return None


external_css = [
    # Normalize the CSS
    "https://cdnjs.cloudflare.com/ajax/libs/normalize/7.0.0/normalize.min.css",
    # Fonts
    "https://fonts.googleapis.com/css?family=Open+Sans|Roboto"
    "https://maxcdn.bootstrapcdn.com/font-awesome/4.7.0/css/font-awesome.min.css",
    # For production
    "https://cdn.rawgit.com/xhlulu/0acba79000a3fd1e6f552ed82edb8a64/raw/dash_template.css",
    # Custom CSS
    "https://cdn.rawgit.com/xhlulu/dash-image-processing/1d2ec55e/custom_styles.css",
    #"https://cdn.rawgit.com/plotly/dash-app-stylesheets/2d266c578d2a6e8850ebce48fdb52759b2aef506/stylesheet-oil-and-gas.css",
    #"https://cdn.rawgit.com/amadoukane96/d930d574267b409a1357ea7367ac1dfc/raw/1108ce95d725c636e8f75e1db6e61365c6e74c8a/web_trader.css",
    #"https://codepen.io/plotly/pen/YeqjLb.css",
    ]



#app.css.append_css({"relative_package_path": __name__ + 'styles.css'})
#dcc._css_dist[0]['relative_package_path'].append('styles.css')
for css in external_css:
    app.css.append_css({"external_url": css})

#app.css.append_css({"external_url": "http://styles.css"})
if __name__ == '__main__':
    app.run_server(debug=True)
