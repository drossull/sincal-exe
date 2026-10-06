// Classic Explorer verbs receive the complete IShellItemArray in one invocation.
// No CAD, PowerShell, or drawing operations are performed inside Explorer.
#include <windows.h>
#include <shobjidl.h>
#include <shlobj.h>
#include <shlwapi.h>
#include <shellapi.h>
#include <wrl.h>
#include <atomic>
#include <filesystem>
#include <string>
#include <vector>
using namespace Microsoft::WRL;
static HMODULE module;
static std::atomic<long> objects{0}, locks{0};
static const wchar_t* actions[] = {L"setup",L"plot",L"publish",L"ze",L"purge"};
static const wchar_t* titles[] = {L"Configurar A1",L"Plotear a PDF",L"Configurar A1 y plotear",L"Encuadrar y guardar",L"Limpiar y guardar"};
// Five stable CLSIDs: {8549E221-34D5-4E21-937C-22D8F0300101} through 0105.
static CLSID id(int i) { return {0x8549e221,0x34d5,0x4e21,{0x93,0x7c,0x22,0xd8,0xf0,0x30,0x01,(BYTE)(i+1)}}; }
static std::wstring quoteJson(const std::wstring& s) {
    std::wstring out=L"\"";
    for(auto c:s) { if(c==L'\\'||c==L'"')out+=L'\\'; if(c<32) { wchar_t buf[7]; swprintf_s(buf,L"\\u%04x",(unsigned)c);out+=buf; } else out+=c; }
    return out+L"\"";
}
class Command final : public RuntimeClass<RuntimeClassFlags<ClassicCom>, IExplorerCommand> {
    int action;
public:
    Command(int a):action(a){++objects;} ~Command(){--objects;}
    IFACEMETHODIMP GetTitle(IShellItemArray*,LPWSTR* out) override {return SHStrDupW(titles[action],out);}
    IFACEMETHODIMP GetIcon(IShellItemArray*,LPWSTR* out) override {*out=nullptr;return E_NOTIMPL;}
    IFACEMETHODIMP GetToolTip(IShellItemArray*,LPWSTR* out) override {return SHStrDupW(L"Revisar los DWG seleccionados en SINCAL Suite",out);}
    IFACEMETHODIMP GetCanonicalName(GUID* out) override {*out=id(action);return S_OK;}
    IFACEMETHODIMP GetState(IShellItemArray* items,BOOL,EXPCMDSTATE* state) override {
        DWORD n=0;*state=(items&&SUCCEEDED(items->GetCount(&n))&&n>0&&n<=1000)?ECS_ENABLED:ECS_DISABLED;return S_OK;
    }
    IFACEMETHODIMP GetFlags(EXPCMDFLAGS* out) override {*out=ECF_DEFAULT;return S_OK;}
    IFACEMETHODIMP EnumSubCommands(IEnumExplorerCommand** out) override {*out=nullptr;return E_NOTIMPL;}
    IFACEMETHODIMP Invoke(IShellItemArray* items,IBindCtx*) override {
        try {
            DWORD count=0;if(!items||FAILED(items->GetCount(&count))||count==0||count>1000)return E_INVALIDARG;
            std::wstring json=L"{\"operation\":"+quoteJson(actions[action])+L",\"files\":[";
            for(DWORD i=0;i<count;++i){
                ComPtr<IShellItem> item;PWSTR name=nullptr;
                HRESULT hr=items->GetItemAt(i,&item);if(FAILED(hr))return hr;
                hr=item->GetDisplayName(SIGDN_FILESYSPATH,&name);if(FAILED(hr))return hr;
                std::wstring path(name);CoTaskMemFree(name);
                if(_wcsicmp(std::filesystem::path(path).extension().c_str(),L".dwg"))return E_INVALIDARG;
                if(i)json+=L",";json+=quoteJson(path);
            }json+=L"]}";
            PWSTR local=nullptr;HRESULT hr=SHGetKnownFolderPath(FOLDERID_LocalAppData,0,nullptr,&local);if(FAILED(hr))return hr;
            std::filesystem::path folder=std::filesystem::path(local)/L"SINCAL"/L"shell-requests";CoTaskMemFree(local);
            std::filesystem::create_directories(folder);
            GUID guid;hr=CoCreateGuid(&guid);if(FAILED(hr))return hr;wchar_t uuid[40];StringFromGUID2(guid,uuid,40);
            auto request=folder/(std::wstring(uuid)+L".json");
            int size=WideCharToMultiByte(CP_UTF8,0,json.data(),(int)json.size(),nullptr,0,nullptr,nullptr);
            std::string bytes(size,'\0');WideCharToMultiByte(CP_UTF8,0,json.data(),(int)json.size(),bytes.data(),size,nullptr,nullptr);
            HANDLE file=CreateFileW(request.c_str(),GENERIC_WRITE,0,nullptr,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,nullptr);
            if(file==INVALID_HANDLE_VALUE)return HRESULT_FROM_WIN32(GetLastError());
            DWORD written=0;BOOL ok=WriteFile(file,bytes.data(),size,&written,nullptr);CloseHandle(file);
            if(!ok||written!=(DWORD)size){DeleteFileW(request.c_str());return E_FAIL;}
            wchar_t dll[32768];DWORD length=GetModuleFileNameW(module,dll,32768);if(!length||length>=32768)return E_FAIL;
            auto exe=std::filesystem::path(dll).parent_path()/L"SINCAL.exe";
            std::wstring args=L"--shell-request \""+request.wstring()+L"\"";
            auto result=(INT_PTR)ShellExecuteW(nullptr,L"open",exe.c_str(),args.c_str(),nullptr,SW_SHOWNORMAL);
            if(result<=32){DeleteFileW(request.c_str());return E_FAIL;}return S_OK;
        } catch(...) {return E_FAIL;}
    }
};
class Factory final : public RuntimeClass<RuntimeClassFlags<ClassicCom>,IClassFactory> {
    int action;
public:
    Factory(int a):action(a){++objects;} ~Factory(){--objects;}
    IFACEMETHODIMP CreateInstance(IUnknown* outer,REFIID iid,void** out) override {
        if(outer)return CLASS_E_NOAGGREGATION;auto command=Make<Command>(action);return command?command.CopyTo(iid,out):E_OUTOFMEMORY;
    }
    IFACEMETHODIMP LockServer(BOOL lock) override {lock?++locks:--locks;return S_OK;}
};
STDAPI DllGetClassObject(REFCLSID clsid,REFIID iid,void** out){
    *out=nullptr;for(int i=0;i<5;++i)if(IsEqualCLSID(clsid,id(i))){auto factory=Make<Factory>(i);return factory?factory.CopyTo(iid,out):E_OUTOFMEMORY;}return CLASS_E_CLASSNOTAVAILABLE;
}
STDAPI DllCanUnloadNow(){return objects==0&&locks==0?S_OK:S_FALSE;}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID){if(reason==DLL_PROCESS_ATTACH){module=instance;DisableThreadLibraryCalls(instance);}return TRUE;}
