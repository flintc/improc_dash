


def session_id_div(session_id,**kwargs):
    return html.Div(session_id, **kwargs)

def make_h2(text,**kwargs):
    return html.H2(
            text,
            **kwargs
    )

def make_img(src,**kwargs):
    return html.Img(
        src=src,
        **kwargs
    )

def banner( h2, img, **kwargs ):
    return html.Div([
        h2,
        img
    ],
        **kwargs
    )


