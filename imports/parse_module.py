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


def compile_lua(main_path, src_path, dst_path):
    # Register compiletime vars and funcs.
    lua = cl.init_lua(src_path)
    cl.execute(lua, '__src_dir = \'' + src_path.replace('\\', '\\\\') + '\'')
    cl.execute(lua, '__dst_dir = \'' + dst_path.replace('\\', '\\\\') + '\'')

    # Run main file.
    full_src_path = os.path.join(src_path, main_path)
    with open(full_src_path, 'r') as file:
        main_content = file.read()
    cl.execute(lua,lua_code.LUA_COMPILETIME + '\n' + main_content)

    print('Used modules:')
    require_list = ['war3map']
    for k in lua.globals().__compile_data.require_list:
        val = lua.globals().__compile_data.require_list[k]
        if val in require_list:
            require_list.remove(val)
        require_list.append(val)

    cl.execute(lua, 'local tmp = \'\'')
    trees = load_modules(require_list, src_path)
    for i, tree in enumerate(trees):
        res_num = 1
        results = '__compile_data.result[\'%s\']' % tree[0]
        for node in ast.walk(tree[1]):
            if isinstance(node, ast.Call) and ats.node_to_str(node.func) == 'compiletime':
                #val = cl.eval(lua, ats.node_to_str(ast.Block(node.args)))
                val = cl.eval(lua, results + '[' + str(res_num) + ']')
                #print(tree[0], val)
                find_node.change_node(tree[1], node, val)
                res_num += 1
        trees[i] = (tree[0], content_to_function(tree[0], tree[1]))
        #print(ats.node_to_str(trees[i][1]))
    # Add require function for runtime
    require_tree = ast.parse(lua_code.LUA_REQUIRE)
    trees.insert(0, ('Require function', require_tree))
    result = ats.node_to_str(link_content(trees))
    with open(os.path.join(dst_path, 'war3map.lua'), 'w') as file:
        file.write(result)

    # Get compiletime results.
    #tree_visitor = ast.WalkVisitor()
    #tree_visitor.visit(content)
    #num = 0
    #for node in tree_visitor.nodes:
    #    if isinstance(node, ast.Call) and ats.node_to_str(node.func) == 'compiletime':
    #        #val = cl.eval(lua, ats.node_to_str(ast.Block(node.args)))
    #        num += 1
    #        val = cl.get_compile_res(lua, num)
    #        find_node.change_node(content, node, val)
    #        #print(ats.node_to_str(val))
    #print('\n\n')
    #print(ats.node_to_str(content))


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

