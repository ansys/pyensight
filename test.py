from ansys.pyensight.core import LocalLauncher
from ansys.pyensight.core.session import Session
 
sessions = []
 
session1 = LocalLauncher("C:\\ANSYSDev\\v242\\CEI").start()
sessions.append(session1)
session2 = Session(
    host=session1.hostname,
    secret_key=session1.secret_key,
    sos=session1.sos,
    rest_api=session1.rest_api,
    html_hostname=str(session1.html_hostname),
    html_port=session1.html_port,
    grpc_port=session1._grpc_port,
    ws_port=session1.ws_port,
    session_directory=session1._launcher.session_directory
)
 
sessions.append(session2)
session2._halt_ensight_on_close = True
session2._launcher._sessions = [session2]
 
#### your code ####
 
 
session2.close()
 
# cleanup
 
for _session in sessions:
    del _session