## Live2D Proprietary Software License

Live2D Cubism Core is available under Live2D Proprietary Software License.

* [Live2D Proprietary Software License Agreement](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_en.html)
* [Live2D Proprietary Software 使用許諾契約書](https://www.live2d.com/eula/live2d-proprietary-software-license-agreement_jp.html)

<!-- merged-from: CHANGELOG.md -->

## Merged from CHANGELOG.md

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).


## 2020-01-30

### Added

* Add static library(.lib) for statically linking DLL.
* Add symbol file for Windows dynamic library (dll).


## 2019-11-19

### Fixed

* Fix linking static libraries for Windows (.lib).


## 2019-11-14

### Added

* Support Visual Studio 2019.
* Support macOS dynamic library (dylib).

### Changed

* Update Windows dynamic library:  Use Visual Studio 2019 for building.

### Security

* Bundle certificate and notary ticket to macOS shared library.


## 2019-09-04

### Added

* Support new Inverted Masking features.
* Support ARM64 architecture for Universal Windows Platform.

### Changed

* Upgrade Core version to 04.00.0000 (67108864). This upgrade is following Cubism Editor 4.0 features.
* Add calling convention for *Windows/x86 DLL* only.

### Removed

* Remove bitcode binary due to suspension of *Cubism Bindings.*


## 2019-04-09

### Added

* Support Universal Windows Platform for Windows Store Application.


## 2019-01-31

### Added

* Add API to get the parent part of the specified part.
* Add API to get moc3 version.


## 2018-12-20

### Added

* [Native] Add new function: `csmGetPartParentPartIndices`.
* [Native, 3.3 Support] Support new Warp Deformer features.

### Changed

* Upgrade Core version to 03.03.0000 (50528256). This upgrade is following Cubism Editor 3.3 features.


## 2018-08-22

### Added

* [Native] Add support for Neon.


## 2018-05-14

### Added

* [Native] Add Windows **Visual C++ 2013** library.
* [Windows] Add runtime library choice `MT`, `MD`, `MTd`, `MDd`.
* [iOS] Add support for iPhone Simulator SDK.

### Fixed

* Fix an error occurred when linking libraries for Android `arm64-v8a`.


## 2017-11-17

### Fixed

* Fix processing of vertex index.


## 2017-10-05

### Added

* Provide bitcode for iOS.


## 2017-08-09

### Added

* [Native] Add Android *arm64-v8a* ABI library.

### Fixed

* Fix drawing order in certain scenarios.


## 2017-07-12

### Added

* Add experimental support for Emscripten.
* Add `CHANGELOG.md`.

### Fixed

* Fix access violation in certain scenarios.
* Fix update result in certain scenarios.


## 2017-05-02

### Added

* [Native] Add experimental support for Raspberry PI.
* Add `README.md`.

<!-- merged-from: README.md -->

## Merged from README.md

# Live2D Cubism Core

This folder contains core library files for developing JavaScript or TypeScript applications.


## File List

### live2dcubismcore.d.ts

This file contains typescript type information about `live2dcubismcore.js`.
Use this file with `live2dcubismcore.js` when developing with TypeScript.

### live2dcubismcore.js

This file contains Cubism Core features and some wrapper features.
Use this file when developing with JavaScript.

### live2dcubismcore.js.map

This file is the source map between `live2dcubismcore.d.ts` and `live2dcubismcore.js`.
Use this file when debugging.

### live2dcubismcore.min.js

This file is minified of `live2dcubismcore.js`.
Use this file in production.
