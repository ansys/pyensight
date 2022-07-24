"""Renderable module

Interface to create objects in the EnSight session that can be displayed
via HTML over the websocketserver interface.
"""
import os
from typing import Optional
import uuid


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

    def __init__(self, session: "pyansys.Session") -> None:
        self._session = session
        self._filename_index: int = 0

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
        url = f"{self._session.secret_key}_{self._filename_index}{suffix}"
        # filename = os.path.join(self._session.launcher.session_directory, url)
        filename = self._session.launcher.session_directory + "/" + url
        self._filename_index += 1
        url = f"http://{self._session.hostname}:{self._session.html_port}/{url}"
        return filename, url

    def _wrap_with_page(self, html: str, filename: str, url: str, suffix: str) -> str:
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
            filename:
                The server (disk) filename that needs to be wrapper by HTML
            url:
                The URL corresponding to 'filename'
            suffix:
                The suffix present in filename and url.  For example ".png"

        Returns:
            The URL to the generated .html file
        """
        # save "html" into a file on the remote server with filename .html
        remote_html_filename = filename.replace(suffix, ".html")

        cmd = f'open(r"""{remote_html_filename}""", "w").write("""{html}""")'
        self._session.grpc.command(cmd, do_eval=False)
        return url.replace(suffix, ".html")

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
        name += f"'website', 'static', 'website', 'content', 'bootstrap.min.css')"
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

    def webgl(self) -> str:
        """Render a webgl iframe

        Render an AVZ file on the EnSight host system and make it available via
        a webpage.

        Returns:
            A URL to a webpage containing the avz interactive viewer
        """
        filename, url = self._generate_filename(".avz")
        # save the .avz file
        self._session.grpc.command("ensight.part.select_all()", do_eval=False)
        self._session.grpc.command('ensight.savegeom.format("avz")', do_eval=False)
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
