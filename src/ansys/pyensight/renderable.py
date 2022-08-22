"""Renderable module

Interface to create objects in the EnSight session that can be displayed
via HTML over the websocketserver interface.
"""
import os
from typing import Any, Optional
import uuid
import webbrowser


class Renderable:
    """Generate HTML pages for renderable entities

    This class provides the underlying HTML remote webpage generation for
    the Session 'show()' method.  The approach is to generate the renderable
    in the EnSight session and make the artifacts available via the websocketserver.
    The artifacts are then wrapped with simple HTML pages (also served up by
    websocket server) which can be used to populate iframes, etc.

    Args:
        session:
            The pyansys session to generate the renderables for
    """
    def __init__(self, session: "pyansys.Session", cell_handle: Optional[Any] = None,
                 width: Optional[int] = None, height: Optional[int] = None,
                 temporal: bool = False, aa: int = 1) -> None:
        self._session = session
        self._filename_index: int = 0
        self._guid = str(uuid.uuid1()).replace("-", "")
        self._cell_handle = cell_handle
        self._url: Optional[str] = None
        self._url_remote_pathname: Optional[str] = None
        self._rendertype: str = ""
        # Common attributes
        self._width: Optional[int] = width
        self._height: Optional[int] = height
        self._temporal: bool = temporal
        self._aa: int = aa

    def _generate_filename(self, suffix: str) -> (str, str):
        """Create new session specific files and urls

        Every time this method is called, a new filename (on the EnSight host)
        and the associated URL for that file are generated.  The caller
        provides the suffix for the names.

        Args:
             suffix:
                The suffix to be appended to the names.  For example: ".png"
        Returns:
            the filename to use on the host system and the URL that accesses the
            file via REST calls to websocketserver
        """
        filename = f"{self._session.secret_key}_{self._guid}_{self._filename_index}{suffix}"
        # pathname = os.path.join(self._session.launcher.session_directory, filename)
        pathname = f"{self._session.launcher.session_directory}/{filename}"
        self._filename_index += 1
        return pathname, filename

    def _generate_url(self):
        # On the remote system:
        #   {session_directory}/{session}_{guid}_{index}_{type}.html
        # The URL to the file:
        #   http://{system}:{websocketserverhtml}/{session}_{guid}_{index}_{type}.html
        suffix = f"_{self._rendertype}.html"
        remote_pathname, _ = self._generate_filename(suffix)
        simple_filename = f"{self._session.secret_key}_{self._guid}_{self._filename_index}{suffix}"
        url = f"http://{self._session.hostname}:{self._session.html_port}/{simple_filename}"
        self._url = url
        self._url_remote_pathname = remote_pathname

    def _save_remote_html_page(self, html: str) -> None:
        """Create an HTML webpage on the remote host

        Given a snippet of HTML and the parameters passed to _generate_filename,
        create a new file on the remote server with the same name as the filename
        but the extension replaced with ".html".  The contents of html will be
        written into the serve .html file.  The URL to the resulting file is
        returned.  The most common use is to generate an "iframe" wrapper around
        some html.

        Args:
            html:
                The HTML snippet to be wrapped remotely

        """
        # save "html" into a file on the remote server with filename .html
        cmd = f'open(r"""{self._url_remote_pathname}""", "w").write("""{html}""")'
        self._session.grpc.command(cmd, do_eval=False)

    def display(self) -> None:
        if self._url:
            webbrowser.open(self._url)

    @property
    def url(self) -> str:
        return self._url

    def _default_size(self, width: int, height: int):
        out_w = self._width
        if out_w is None:
            out_w = width
        out_h = self._height
        if out_h is None:
            out_h = height
        return out_w, out_h

    def update(self) -> None:
        if self._cell_handle:
            from IPython.display import IFrame
            width, height = self._default_size(800, 600)
            self._cell_handle.display(IFrame(src=self._url, width=width, height=height))

    def deep_pixel(self, width: Optional[int], height: Optional[int], aa: int = 1) -> str:
        """Render a deep pixel iframe

        Render a deep pixel image on the EnSight host system and make it available via
        a webpage.

        Args:
            width:
                The width of the image
            height:
                The height of the image
            aa:
                Number of antialiasing passes to use

        Returns:
            A URL to a webpage containing the image content
        """
        filename, url = self._generate_filename(".tif")
        guid = str(uuid.uuid1()).replace("-", "")
        # save the image file
        if width is None:
            width = 1920
        if height is None:
            height = 1080
        deep = "enhanced=1"
        cmd = f'ensight.render({width},{height},num_samples={aa},{deep}).save(r"""{filename}""")'
        self._session.cmd(cmd)
        html_source = os.path.join(os.path.dirname(__file__), "deep_pixel_view.html")
        with open(html_source, "r") as fp:
            html = fp.read()
        # copy some files from Nexus
        cmd = "import shutil, enve, ceiversion, os.path\n"
        for script in ["jquery-3.4.1.min.js", "geotiff.js", "geotiff_nexus.js", "bootstrap.min.js"]:
            name = "os.path.join(enve.home(), f'nexus{ceiversion.nexus_suffix}', 'django', "
            name += f"'website', 'static', 'website', 'scripts', '{script}')"
            cmd += f'shutil.copy({name}, r"""{self._session.launcher.session_directory}""")\n'
        name = "os.path.join(enve.home(), f'nexus{ceiversion.nexus_suffix}', 'django', "
        name += "'website', 'static', 'website', 'content', 'bootstrap.min.css')"
        cmd += f'shutil.copy({name}, r"""{self._session.launcher.session_directory}""")\n'
        self._session.cmd(cmd, do_eval=False)
        # replace some bits in the HTML
        html = html.replace("TIFF_URL", url)
        html = html.replace("ITEMID", guid)
        # save the HTML
        return self._wrap_with_page(html, filename, url, ".tif")

    def image(self, width: Optional[int], height: Optional[int], aa: int = 1) -> str:
        """Render an image iframe

        Render an image on the EnSight host system and make it available via
        a webpage.

        Args:
            width:
                The width of the image
            height:
                The height of the image
            aa:
                Number of antialiasing passes to use

        Returns:
            A URL to a webpage containing the image content
        """
        filename, url = self._generate_filename(".png")
        # save the image file
        if width is None:
            width = 1920
        if height is None:
            height = 1080
        cmd = f'ensight.render({width},{height},num_samples={aa}).save(r"""{filename}""")'
        self._session.cmd(cmd)
        # generate HTML page with file references local to the websocketserver root
        url_path = os.path.basename(url)
        html = f'<img src="/{url_path}">\n'
        return self._wrap_with_page(html, filename, url, ".png")

    def webgl(self, temporal: bool = False) -> str:
        """Render a webgl iframe

        Render an AVZ file on the EnSight host system and make it available via
        a webpage.

        Args:
            temporal:
                If True, save all timesteps.  If False, just the current one.

        Returns:
            A URL to a webpage containing the avz interactive viewer
        """
        filename, url = self._generate_filename(".avz")
        # save the .avz file
        self._session.grpc.command("ensight.part.select_all()", do_eval=False)
        self._session.grpc.command('ensight.savegeom.format("avz")', do_eval=False)
        ts = self._session.ensight.objs.core.TIMESTEP
        st = ts
        en = ts
        if temporal:
            st, en = self._session.ensight.objs.core.TIMESTEP_LIMITS
        self._session.grpc.command(f"ensight.savegeom.begin_step({st})", do_eval=False)
        self._session.grpc.command(f"ensight.savegeom.end_step({en})", do_eval=False)
        self._session.grpc.command("ensight.savegeom.step_by(1)", do_eval=False)
        cmd = f'ensight.savegeom.save_geometric_entities(r"""{filename}""")'
        self._session.grpc.command(cmd, do_eval=False)
        # generate HTML page with file references local to the websocketserver root
        url_path = os.path.basename(url)
        html = "<script src='/ansys/nexus/viewer-loader.js'></script>\n"
        html += f"<ansys-nexus-viewer src='/{url_path}'></ansys-nexus-viewer>\n"
        return self._wrap_with_page(html, filename, url, ".avz")

    def vnc(self) -> str:
        """Generate an HTML page to access the VNC renderer

        Generate a URL that can be used to connect to the EnSight VNC remote image renderer.

        Returns:
            A URL to a webpage containing the vnc renderer
        """
        url = f"http://{self._session.hostname}:{self._session.html_port}"
        url += "/ansys/nexus/novnc/vnc_envision.html"
        url += f"?autoconnect=true&host={self._session.hostname}&port={self._session.ws_port}"
        return url


class RenderableImage(Renderable):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._rendertype = 'image'
        self._generate_url()
        pathname, filename = self._generate_filename(".png")
        self._png_pathname = pathname
        self._png_filename = filename
        self.update()

    def update(self):
        # save the image file
        w, h = self._default_size(1920, 1080)
        cmd = f'ensight.render({w},{h},num_samples={self._aa}).save(r"""{self._png_pathname}""")'
        self._session.cmd(cmd)
        # generate HTML page with file references local to the websocketserver root
        html = f'<img src="/{self._png_filename}">\n'
        # refresh the remote HTML
        self._save_remote_html_page(html)
        super().update()


class RenderableDeepPixel(Renderable):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._rendertype = 'deep_pixel'
        self._generate_url()
        pathname, filename = self._generate_filename(".tif")
        self._tif_pathname = pathname
        self._tif_filename = filename
        self.update()

    def update(self):
        # save the image file
        w, h = self._default_size(1920, 1080)
        deep = "enhanced=1"
        cmd = f'ensight.render({w},{h},num_samples={aa},{deep}).save(r"""{self._tif_pathname}""")'
        self._session.cmd(cmd)
        html_source = os.path.join(os.path.dirname(__file__), "deep_pixel_view.html")
        with open(html_source, "r") as fp:
            html = fp.read()
        # copy some files from Nexus
        cmd = "import shutil, enve, ceiversion, os.path\n"
        for script in ["jquery-3.4.1.min.js", "geotiff.js", "geotiff_nexus.js", "bootstrap.min.js"]:
            name = "os.path.join(enve.home(), f'nexus{ceiversion.nexus_suffix}', 'django', "
            name += f"'website', 'static', 'website', 'scripts', '{script}')"
            cmd += f'shutil.copy({name}, r"""{self._session.launcher.session_directory}""")\n'
        name = "os.path.join(enve.home(), f'nexus{ceiversion.nexus_suffix}', 'django', "
        name += "'website', 'static', 'website', 'content', 'bootstrap.min.css')"
        cmd += f'shutil.copy({name}, r"""{self._session.launcher.session_directory}""")\n'
        self._session.cmd(cmd, do_eval=False)
        # replace some bits in the HTML
        tiff_url = f"http://{self._session.hostname}:{self._session.html_port}/{self._tif_filename}"
        html = html.replace("TIFF_URL", tiff_url)
        html = html.replace("ITEMID", self._guid)
        # refresh the remote HTML
        self._save_remote_html_page(html)
        super().update()


class RenderableWebGL(Renderable):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._rendertype = 'webgl'
        self._generate_url()
        pathname, filename = self._generate_filename(".avz")
        self._avz_pathname = pathname
        self._avz_filename = filename
        self.update()

    def update(self):
        # save the .avz file
        self._session.grpc.command("ensight.part.select_all()", do_eval=False)
        self._session.grpc.command('ensight.savegeom.format("avz")', do_eval=False)
        ts = self._session.ensight.objs.core.TIMESTEP
        st = ts
        en = ts
        if self._temporal:
            st, en = self._session.ensight.objs.core.TIMESTEP_LIMITS
        self._session.grpc.command(f"ensight.savegeom.begin_step({st})", do_eval=False)
        self._session.grpc.command(f"ensight.savegeom.end_step({en})", do_eval=False)
        self._session.grpc.command("ensight.savegeom.step_by(1)", do_eval=False)
        cmd = f'ensight.savegeom.save_geometric_entities(r"""{self._avz_pathname}""")'
        self._session.grpc.command(cmd, do_eval=False)
        # generate HTML page with file references local to the websocketserver root
        html = "<script src='/ansys/nexus/viewer-loader.js'></script>\n"
        html += f"<ansys-nexus-viewer src='/{self._avz_filename}'></ansys-nexus-viewer>\n"
        # refresh the remote HTML
        self._save_remote_html_page(html)
        super().update()


class RenderableVNC(Renderable):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._rendertype = 'remote'
        self.update()

    def update(self):
        url = f"http://{self._session.hostname}:{self._session.html_port}"
        url += "/ansys/nexus/novnc/vnc_envision.html"
        url += f"?autoconnect=true&host={self._session.hostname}&port={self._session.ws_port}"
        self._url = url
        super().update()
