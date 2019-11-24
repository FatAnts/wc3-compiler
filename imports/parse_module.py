'''

'''
import os
import platform

import pathlib
from luaparser import ast

from . import lua_code
from . import ast_to_string as ats
from . import find_node
from . import call_lua as cl


def content_to_function(module_name, tree):
    res = tree
    if module_name != 'war3map':
        func_tree = ast.parse(lua_code.LUA_REQUIRE_FUNC).body.body[0]
        func_tree.values[0].body = tree.body
        func_tree.targets[0].idx = ast.String(module_name)
        res = func_tree
    return res


def load_modules(modules_list, src_path):
    tree_list = []
    for module in modules_list:
        rel_path = ats.name_to_module_path(module)
        full_path = os.path.join(src_path, rel_path)
        with open(full_path, 'r') as file:
            content = file.read()
        tree_list.append((module, ast.parse(content)))
    return tree_list


def get_require_list(module, src_path, require_list):
    rel_path = ats.name_to_module_path(module)
    full_path = os.path.join(src_path, rel_path)

    if module in require_list:
        return
    require_list.append(module)

    with open(full_path, 'r') as file:
        content = file.read()
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and ats.node_to_str(node.func) == 'require':
            if len(node.args) > 1:
                print('\nError: require function can have only 1 constant string argument')
            else:
                next_modname = ats.node_to_str(node.args[0])[1:-1]
                path = os.path.join(src_path, ats.name_to_module_path(next_modname))
                if not os.path.exists(os.path.join(src_path, path)):
                    print('Error in ' + os.path.join(src_path, ats.name_to_module_path(module)) +
                          '\nCan not find module ' + next_modname)
                    exit(-1)
                get_require_list(next_modname, src_path, require_list)


def compile_lua(src_path, dst_path):
    # Register compiletime vars and funcs.
    lua = cl.init_lua(src_path)
    cl.execute(lua, '_G._src_dir = \'' + src_path.replace('\\', '\\\\') + '\'')
    cl.execute(lua, '_G._dst_dir = \'' + dst_path.replace('\\', '\\\\') + '\'')

    # Run main file.
    cl.execute(lua, lua_code.LUA_COMPILETIME)

    test_list = []
    get_require_list('war3map', src_path, test_list)

    require_list = []
    compiletime_list = []
    for modname in test_list:
        cl.execute(lua, 'require(\'' + modname + '\')')

    print('Used modules:')

    print('  Compiletime:')
    for modname in test_list:
        if not modname.startswith('compiletime.'):
            require_list.append(modname)
        else:
            print('    ' + modname)
            compiletime_list.append(modname)

    trees = load_modules(require_list, src_path)
    print('  Runtime:')
    for i, tree in enumerate(trees):
        res_num = 1
        print('    ' + require_list[i])
        results = '__compile_data.result[\'%s\']' % tree[0]
        for node in ast.walk(tree[1]):
            if isinstance(node, ast.Call) and ats.node_to_str(node.func) == 'compiletime':
                val = cl.eval(lua, results + '[' + str(res_num) + ']')
                find_node.change_node(tree[1], node, val)
                res_num += 1
        trees[i] = (tree[0], content_to_function(tree[0], tree[1]))
    cl.execute(lua, '__finalize()')
    trees.reverse()
    require_tree = ast.parse(lua_code.LUA_REQUIRE)

    trees.insert(0, ('Require function', require_tree))
    result = ats.node_to_str(link_content(trees))
    with open(os.path.join(dst_path, 'war3map.lua'), 'w') as file:
        file.write(result)


def add_extension_functions(file_list, content_list):
    require_tree = ast.parse(lua_code.LUA_REQUIRE)
    content_list.insert(0, require_tree)
    file_list.insert(0, 'Require function')


def link_content(trees):
    l = []
    for tree in trees:
        l.append(tree[1])

    block = ast.Block(l)
    return block

