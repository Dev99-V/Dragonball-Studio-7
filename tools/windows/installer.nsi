; DR7-Studio Windows x64 Installer (NSIS MUI2, LZMA Solid, Per-User No-UAC)
; Built via: makensis -DAPP_VERSION=... -DSTAGE_DIR=... -DICON_PATH=... -DOUT_FILE=... tools/windows/installer.nsi

Unicode true
!include "MUI2.nsh"
!include "FileFunc.nsh"

!ifndef APP_VERSION
  !define APP_VERSION "0.18.0"
!endif

!define APP_NAME "DR7-Studio DragonBall 2D"
!define APP_SHORT "DR7-Studio"
!define APP_PUBLISHER "DR7-Studio"
!define APP_EXE "DR7-Studio.exe"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\DR7-Studio"

Name "${APP_NAME} v${APP_VERSION}"
OutFile "${OUT_FILE}"
InstallDir "$LOCALAPPDATA\Programs\${APP_SHORT}"
InstallDirRegKey HKCU "${UNINST_KEY}" "InstallLocation"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 32

BrandingText "${APP_PUBLISHER} v${APP_VERSION}"

!define MUI_ABORTWARNING
!define MUI_ICON "${ICON_PATH}"
!define MUI_UNICON "${ICON_PATH}"

!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "Mo ${APP_NAME} ngay bay gio"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  File /r "${STAGE_DIR}\*.*"
  File "/oname=dr7_studio.ico" "${ICON_PATH}"

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Start Menu Shortcuts
  CreateDirectory "$SMPROGRAMS\${APP_SHORT}"
  CreateShortCut "$SMPROGRAMS\${APP_SHORT}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\dr7_studio.ico" 0
  CreateShortCut "$SMPROGRAMS\${APP_SHORT}\Uninstall ${APP_SHORT}.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\dr7_studio.ico" 0

  ; Desktop Shortcut
  CreateShortCut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}" "" "$INSTDIR\dr7_studio.ico" 0

  ; Add/Remove Programs Metadata (HKCU - no admin required)
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\dr7_studio.ico"
  WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "EstimatedSize" "$0"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_SHORT}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_SHORT}\Uninstall ${APP_SHORT}.lnk"
  RMDir "$SMPROGRAMS\${APP_SHORT}"

  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${UNINST_KEY}"
SectionEnd
