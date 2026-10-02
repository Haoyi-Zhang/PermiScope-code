#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
from pathlib import Path
OUT=Path(__file__).resolve().parent/'inputs'/'public-slices'
VPATH='services/core/java/com/android/server/vibrator/VibratorManagerService.java'
WPATH='services/core/java/com/android/server/wallpaper/WallpaperManagerService.java'
BASE='https://github.com/aosp-mirror/platform_frameworks_base/blob/android-14.0.0_r1/'
BLOB_SHA1={
    VPATH:'cb7e54dda5279d5e80a34a279fa0bb1a61ece934',
    WPATH:'cd3d603d831a0478aaea4d09e8db8d589c14a9dc',
}
CASES=[
('vibrator-is-vibrating',VPATH,277,282,'mContext.enforceCallingOrSelfPermission','android.Manifest.permission.ACCESS_VIBRATOR_STATE','android.permission.ACCESS_VIBRATOR_STATE','''    public boolean isVibrating(int vibratorId) {
        mContext.enforceCallingOrSelfPermission(
                android.Manifest.permission.ACCESS_VIBRATOR_STATE,
                "isVibrating");
        VibratorController controller = mVibrators.get(vibratorId);
        return controller != null && controller.isVibrating();
'''),
('vibrator-register-listener',VPATH,285,293,'mContext.enforceCallingOrSelfPermission','android.Manifest.permission.ACCESS_VIBRATOR_STATE','android.permission.ACCESS_VIBRATOR_STATE','''    public boolean registerVibratorStateListener(int vibratorId, IVibratorStateListener listener) {
        mContext.enforceCallingOrSelfPermission(
                android.Manifest.permission.ACCESS_VIBRATOR_STATE,
                "registerVibratorStateListener");
        VibratorController controller = mVibrators.get(vibratorId);
        if (controller == null) {
            return false;
        }
        return controller.registerVibratorStateListener(listener);
'''),
('vibrator-unregister-listener',VPATH,296,305,'mContext.enforceCallingOrSelfPermission','android.Manifest.permission.ACCESS_VIBRATOR_STATE','android.permission.ACCESS_VIBRATOR_STATE','''    public boolean unregisterVibratorStateListener(int vibratorId,
            IVibratorStateListener listener) {
        mContext.enforceCallingOrSelfPermission(
                android.Manifest.permission.ACCESS_VIBRATOR_STATE,
                "unregisterVibratorStateListener");
        VibratorController controller = mVibrators.get(vibratorId);
        if (controller == null) {
            return false;
        }
        return controller.unregisterVibratorStateListener(listener);
'''),
('vibrator-set-always-on',VPATH,308,314,'mContext.enforceCallingOrSelfPermission','android.Manifest.permission.VIBRATE_ALWAYS_ON','android.permission.VIBRATE_ALWAYS_ON','''    public boolean setAlwaysOnEffect(int uid, String opPkg, int alwaysOnId,
            @Nullable CombinedVibration effect, @Nullable VibrationAttributes attrs) {
        Trace.traceBegin(Trace.TRACE_TAG_VIBRATOR, "setAlwaysOnEffect");
        try {
            mContext.enforceCallingOrSelfPermission(
                    android.Manifest.permission.VIBRATE_ALWAYS_ON,
                    "setAlwaysOnEffect");
'''),
('vibrator-vibrate-internal',VPATH,360,365,'mContext.enforceCallingOrSelfPermission','android.Manifest.permission.VIBRATE','android.permission.VIBRATE','''    HalVibration vibrateInternal(int uid, int displayId, String opPkg,
            @NonNull CombinedVibration effect, @Nullable VibrationAttributes attrs,
            String reason, IBinder token) {
        Trace.traceBegin(Trace.TRACE_TAG_VIBRATOR, "vibrate, reason = " + reason);
        try {
            mContext.enforceCallingOrSelfPermission(android.Manifest.permission.VIBRATE, "vibrate");
'''),
('vibrator-cancel',VPATH,442,447,'mContext.enforceCallingOrSelfPermission','android.Manifest.permission.VIBRATE','android.permission.VIBRATE','''    public void cancelVibrate(int usageFilter, IBinder token) {
        Trace.traceBegin(Trace.TRACE_TAG_VIBRATOR, "cancelVibrate");
        try {
            mContext.enforceCallingOrSelfPermission(
                    android.Manifest.permission.VIBRATE,
                    "cancelVibrate");
'''),
('wallpaper-clear',WPATH,1837,1840,'checkPermission','android.Manifest.permission.SET_WALLPAPER','android.permission.SET_WALLPAPER','''    public void clearWallpaper(String callingPackage, int which, int userId) {
        if (DEBUG) Slog.v(TAG, "clearWallpaper");
        checkPermission(android.Manifest.permission.SET_WALLPAPER);
        if (!isWallpaperSupported(callingPackage) || !isSetWallpaperAllowed(callingPackage)) {
'''),
('wallpaper-dimension-hints',WPATH,1986,1988,'checkPermission','android.Manifest.permission.SET_WALLPAPER_HINTS','android.permission.SET_WALLPAPER_HINTS','''    public void setDimensionHints(int width, int height, String callingPackage, int displayId)
            throws RemoteException {
        checkPermission(android.Manifest.permission.SET_WALLPAPER_HINTS);
'''),
('wallpaper-display-padding',WPATH,2071,2072,'checkPermission','android.Manifest.permission.SET_WALLPAPER_HINTS','android.permission.SET_WALLPAPER_HINTS','''    public void setDisplayPadding(Rect padding, String callingPackage, int displayId) {
        checkPermission(android.Manifest.permission.SET_WALLPAPER_HINTS);
'''),
('wallpaper-lock-callback',WPATH,2519,2524,'checkPermission','android.Manifest.permission.INTERNAL_SYSTEM_WINDOW','android.permission.INTERNAL_SYSTEM_WINDOW','''    public boolean setLockWallpaperCallback(IWallpaperManagerCallback cb) {
        checkPermission(android.Manifest.permission.INTERNAL_SYSTEM_WINDOW);
        synchronized (mLock) {
            mKeyguardListener = cb;
        }
        return true;
'''),
('wallpaper-set-dim',WPATH,2634,2635,'checkPermission','android.Manifest.permission.SET_WALLPAPER_DIM_AMOUNT','android.permission.SET_WALLPAPER_DIM_AMOUNT','''    public void setWallpaperDimAmountForUid(int uid, float dimAmount) {
        checkPermission(android.Manifest.permission.SET_WALLPAPER_DIM_AMOUNT);
'''),
('wallpaper-set',WPATH,2800,2805,'checkPermission','android.Manifest.permission.SET_WALLPAPER','android.permission.SET_WALLPAPER','''    public ParcelFileDescriptor setWallpaper(String name, String callingPackage,
            Rect cropHint, boolean allowBackup, Bundle extras, int which,
            IWallpaperManagerCallback completion, int userId) {
        userId = ActivityManager.handleIncomingUser(getCallingPid(), getCallingUid(), userId,
                false /* all */, true /* full */, "changing wallpaper", null /* pkg */);
        checkPermission(android.Manifest.permission.SET_WALLPAPER);
'''),
]
def source(case,permission):
    c='SliceService';sid=case.replace('-','_')
    return {'language':'bfil-1','permissions':[permission],
      'classes':[{'name':c,'super':None,'fields':[],'methods':[{'name':'api','params':[],'returns':None,'locals':[],
        'body':[{'id':sid+'_check','op':'check','permission':permission},{'id':sid+'_return','op':'return','src':None}]}]}],
      'services':[{'name':'slice_service','declared_class':c,'implementation_class':c}],
      'entries':[{'name':'SliceAPI','service':'slice_service','selector':'api','arg_classes':[]}]}
OUT.mkdir(parents=True,exist_ok=True)
for case,path,start,end,primitive,literal,permission,text in CASES:
    record={'id':case,'provenance':{'repository':'aosp-mirror/platform_frameworks_base','tag':'android-14.0.0_r1',
      'path':path,'start_line':start,'end_line':end,'url':BASE+path+f'#L{start}-L{end}','license':'Apache-2.0',
      'file_blob_sha1':BLOB_SHA1[path],'excerpt_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest()},
      'excerpt':text,'anchor':{'primitive':primitive,'literal':literal,'permission':permission},'source':source(case,permission)}
    (OUT/(case+'.json')).write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
print(len(CASES))
