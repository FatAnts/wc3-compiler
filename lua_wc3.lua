local is_compiletime = true
local compiletime_packages = {}
local runtime_packages = {}
local src_dir = 'empty'
local dst_dir = 'empty'
local sep = package.config:sub(1,1)

---@return boolean
function IsCompiletime()
    return is_compiletime
end

function GetSrcDir()
    return src_dir
end

function GetDstDir()
    return dst_dir
end

local loading_modules = {}
local original_require = _G.require
local inside_compiletime_function = false
local package_func_code = [[
package_files['%s'] = function()
    %s
end
]]
local runtime_code = [[
lua_wc3 = {}
package_files = {}

do
    local is_compiletime = false

    function isCompiletime()
        return is_compiletime
    end

    loaded_packages = {}
    function require(package_name)
        if not loaded_packages[package_name] then
            loaded_packages[package_name] = package_files[package_name]() or true
        end
        return loaded_packages[package_name]
    end
end

]]

---@param src string
---@param dst string
local function compile(src, dst)
    src_dir = src..sep
    dst_dir = dst..sep
    assert(require('war3map'))

    local res = runtime_packages[name2path('war3map')]
    runtime_packages[name2path('war3map')] = nil
    for k, v in pairs(runtime_packages) do
        res = string.format(package_func_code,
                            path2name(k), v:gsub('\n', '\n\t'))..'\n'..res
    end
    res = runtime_code..res
    writeFile(res, dst_dir..sep..'war3map.lua')
end

function require(package_name)
    local info = debug.getinfo(2, 'lS')

    if not type(package_name) == 'string' then
        error(string.format('require function got non string value. %s:%s', info.source, info.currentline))
    end

    if info.name then
        error(string.format('require function can be used in main file chunk only. %s:%d', info.source, info.currentline))
    end

    if loading_modules[package_name] then
        return
    end

    --print(package_name, inside_compiletime_function)
    local path = name2path(package_name)
    if inside_compiletime_function then
        if not compiletime_packages[path] then
            print('Compiletime require:', path)
            compiletime_packages[path] = readFile(path)
        end
    else
        if not runtime_packages[path] then
            print('Runtime require:', path)
            runtime_packages[path] = readFile(path)
        end
    end

    loading_modules[package_name] = true
    local res = original_require(package_name)
    loading_modules[package_name] = false
    return res
end


local function checkCompiletimeResult(result)
    local res_type = type(result)
    if res_type == 'string' or res_type == 'number' then
        return true
    elseif res_type == 'table' then
        for k,v in pairs(result) do
            if not checkCompiletimeResult(k) or not checkCompiletimeResult(v) then
                return false
            end
        end
        return true
    end
    return false
end

local function compiletimeToString(val)
    local t = type(val)
    if t == 'string' then
        return '\''..val..'\''
    elseif t == 'number' then
        return tostring(val)
    elseif t == 'table' then
        local res = '{'
        for k, v in pairs(val) do
            res = res..string.format('[%s] = %s,', compiletimeToString(k), compiletimeToString(v))
        end
        return res..'}'
    end
end

function compiletime(body, ...)
    local info = debug.getinfo(2, 'lSn')

    if inside_compiletime_function then
        error(string.format('compiletime function can not run inside other compiletim function. %s:%d', info.source, info.currentline))
    end
    
    inside_compiletime_function = true

    if not is_compiletime then
        error(string.format('compiletime function can not run in runtime. %s:%d', info.source, info.currentline))
    end

    if info.name then
        error(string.format('compiletime function can be used in main file chunk only. %s:%d', info.source, info.currentline))
    end

    local res
    if type(body) == 'function' then
        res = body(...)
    else
        res = body
    end

    if not checkCompiletimeResult(res) then
        error(string.format('compiletime function can return only string, number or table with strings, numbers and tables. %s:%s', info.source, info.currentline))
    end

    local path = src_dir..info.source:sub(4, #info.source)
    if runtime_packages[path] then
        runtime_packages[path] = string.gsub(runtime_packages[path], 'compiletime%b()', compiletimeToString(res), 1)
        --print(runtime_packages[path])
    end
    if compiletime_packages[path] then
        compiletime_packages[path] = string.gsub(compiletime_packages[path], 'compiletime%b()', compiletimeToString(res), 1)
        --print(compiletime_packages[path])
    end

    inside_compiletime_function = false

    return res
end

---@param package_name string
function name2path(package_name)
    return src_dir..package_name:gsub('%.', sep)..'.lua'
end

---@param path string
function path2name(path)
    path = path:gsub(src_dir, '')
    path = string.gsub(path, '\\', '.')
    return path:sub(1, #path - 4)
end

local function file_exists(file)
    local f = io.open(file, "rb")
    if f then
        f:close()
    end
    return f ~= nil
end

function readFile(path)
    if not file_exists(path) then
        local info = debug.getinfo(2, 'lS')
        error(string.format('can not find file. %s:%s', info.source, info.currentline))
    end

    local lines = {}
    for line in io.lines(path) do 
      lines[#lines + 1] = line
    end

    local str = table.concat(lines, '\n')

    local s = string.find(str, '--[[', nil, true)
    while s do
        local e = string.find(str, '%]%]', s)
        str = str:sub(1, s - 1)..str:sub(e + 2, #str)
        s = string.find(str, '--[[', nil, true)
    end

    s = string.find(str, '%-%-')
    while s do
        local e = string.find(str, '\n', s)
        str = str:sub(1, s - 1)..str:sub(e + 1, #str)
        s = string.find(str, '%-%-')
    end

    s = string.find(str, '\n\n')
    while s do
        str = string.gsub(str, '\n\n', '\n')
        s = string.find(str, '\n\n')
    end

    return str
end

function writeFile(str, path)
    local f = io.open(path, "w")
    f:write(str)
    f:close()
end

local __finalize_list = {}
function __finalize()
    for _, fun in pairs(__finalize_list) do
        if type(fun) == 'function' then
            fun()
        end
    end
end

function addCompiletimeFinalize(fun)
    table.insert(__finalize_list, 1, fun)
end