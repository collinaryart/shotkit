"""shotkit: a small CG-pipeline toolkit.

A Pipeline TD's week is mostly small tools around four questions:
  * where does a file live?          -> scaffold.py  (the show tree)
  * is this file named correctly?    -> naming.py    (the studio convention)
  * which version is current?        -> publish.py   (immutable versions + manifests + latest)
  * is this render complete?         -> sequences.py (frame ranges and missing frames)
plus a sanity check inside the DCC   -> maya_check.py (maya.cmds, injected so it is testable without Maya)

Everything here is plain Python 3.9+ with no third-party dependency, so it runs on a Linux
workstation, in a render-farm shell, or inside Maya's own interpreter (mayapy).
"""

__version__ = "0.1.0"
