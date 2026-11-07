Component Launcher release request
Reason: publish latest Workspace main UI fixes: unified Internet & Network navigation plus visible emoji flags for every Firefox server country and selected preview.
Workspace source commit: fb2f37f96137bdbb1b97801527540010498234be
Requested: 2026-10-28
Use official source pin, signing, release receipt and Pantry publication gates. Preserve all local WIP and staged files.

Launcher runtime authority/.NET 8 correction request
Workspace source fix: 6a59557ba7a26ec7f88a100dd0f7295cb0df6536
Requested: 2026-10-29
Use Component Launcher signed build/verify/Publish pipeline only. Keep frozen Bootstrap local-only; never alter private signers or replace pinned native deliveries. Preserve existing Workspace checkout and foreign WIP.

KYRON Web Tabs UI and lazy WebView2 release request
Workspace source commit: cbda556f11724224facf40dab6b47e92076a06ee
Requested: 2026-11-01
Component Launcher only. Render ChatGPT and Spotify as pinned tabs in existing REV chrome; create inactive WebView2 renderer only on first visit. Preserve ChatGPT extension profile, user data, all signed-source/provenance gates and frozen local-only Bootstrap. Build, sign, verify and publish from the exact pinned Workspace main revision; do not include or reset unrelated local WIP.

KYRON retired Windows Core/Tunnel migration and verification cleanup release request
Workspace source commit: cc7da011f3d8af0e6da0bff25f08a341f12be184
Requested: 2026-11-03
Run the official Component Launcher source-pin/prepare/sign/verify/publish workflow for exact current Workspace/main. Runtime is standalone and service-free; preserve frozen Bootstrap as locally signed and never publish Bootstrap bytes to Pantry Core. Keep native Lib unrelated WIP and all foreign state untouched. Respect authenticated canonical signer, protected source and publication gates. Do not bypass unavailable publisher or report install success without a verified consumer smoke.
