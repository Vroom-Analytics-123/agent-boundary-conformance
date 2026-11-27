# FinePrint on agent37.com — the cheapest hosted proof
#
# agent37.com is hosted like the cloud, but the user controls the
# image (a custom Dockerfile template, built with
# `npx agent37 templates build`) and the launch command (a browser TTY
# terminal + an exec API). That is why it is the exception to "hosted
# cannot be walled": the wall can be baked into the template, because
# the template IS the image. (VERIFIED from agent37.com's own ToS,
# blog, docs, GitHub examples, and a founder interview; investigation
# doc §9.)
#
# ## The template
#
# The template is this image — cloud/Dockerfile. Build it the same
# way (`docker build -t fineprint-wall:cloud -f cloud/Dockerfile .`
# after the desktop image), then register it as an agent37 custom
# template. The template's launch command is the agent command; the
# image's ENTRYPOINT is the gate, so the agent starts inside the wall.
#
# ## The one exec call (do this first)
#
# Before shipping the template, run the nested-unshare test inside a
# default-tier instance — in the template's browser terminal:
#
#   unshare --map-root-user --mount sh -c 'mount -t tmpfs tmpfs /tmp && echo OK'
#
# then the wall's T1–T7 smoke test (cloud/nested-unshare-test.sh).
# The default sandbox type is gVisor (`runsc`), and whether `unshare`
# works there is UNVERIFIED — one exec call settles it. If it fails,
# the full-VM tier (Cloud Hypervisor, a real kernel, 2.5x compute)
# runs the wall; the default tier cannot, and the honest fallback
# there is Check-after-the-fact, not a wall.
#
# ## What to ask agent37 before shipping (open question 13)
#
# Their ToS §7 asks whether running a nested sandbox inside your own
# instance counts as "circumventing instance isolation". Ask them
# before shipping the template, not after. Do not ship the template
# until that answer is in hand.
#
# ## What this does not do
#
# - It does not wall the agent37 host, kernel, or sandbox runtime —
#   you control the image and the launch command, not the
#   infrastructure underneath.
# - It does not publish the image anywhere: agent37 builds the
#   template from the Dockerfile you give it. The image is NOT
#   published to GHCR / Docker Hub.
# - Auth: the template's agent needs its own login (BYOK). The same
#   rule as everywhere else — API keys as env vars, or a read-only
#   config-dir mount; never bake a key into the template.
