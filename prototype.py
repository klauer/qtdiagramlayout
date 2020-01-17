import logging
from collections import defaultdict

import qtpynodeeditor
from qtpy import QtWidgets, QtGui, QtCore

invert_direction = {
    'n': 's',
    'e': 'w',
    'w': 'e',
    's': 'n',
    'nw': 'se',
    'ne': 'sw',
    'sw': 'ne',
    'se': 'nw',
}

class Node:
    def __init__(self, idx, shape, *, parent=None):
        self.positioned = False
        self.idx = idx
        self.shape = shape
        self.connections = defaultdict(list)
        self.parent = parent
        self.widget = shape.widget()
        self.group = QtWidgets.QGraphicsItemGroup()
        self.group.addToGroup(self.shape)

    def get_direction_to_child(self, node):
        for direction, nodes in self.connections.items():
            if node in nodes:
                return direction
        raise ValueError('not connected')

    def get_nodes(self):
        nodes_list = []
        for direction, nodes in self.connections.items():
            nodes_list.extend(nodes)

        return nodes_list

    def get_bounding_rect(self):
        x = self.shape.pos().x()
        y = self.shape.pos().y()
        w = self.widget.width()
        h = self.widget.height()
        rect = self.group.boundingRect()
        return x, y, w, h, rect.x(), rect.y(), rect.width(), rect.height()

    def walk_depth_first(self, visited=None):
        if visited is None:
            visited = []
        for direction, nodes in self.connections.items():
            for node in nodes:
                if node in visited:
                    continue
                visited.append(node)
                yield from node.walk_depth_first(visited)
        visited.append(self)
        yield self

    def __repr__(self):
        # return f'<{self.idx} {dict(self.connections)} >'
        return f'<{self.idx} >'

def build_tree(shapes, connections):
    nodes = {idx: Node(idx=idx, shape=shape)
             for idx, shape in shapes.items()
             }

    for node in nodes.values():
        for direction, idx in connections[node.idx].items():
            node.connections[direction].append(nodes[idx])
            nodes[idx].parent = node

    root = [node for node in nodes.values()
            if node.parent is None]

    if len(root) != 1:
        raise ValueError('Not only one root?')

    # print('root is', root[0].idx)
    return root[0]

def calculate_position(parent, node, direction, min_spacing, parent_to_node=True):
    p_x, p_y, p_w, p_h, p_g_x, p_g_y, p_g_w, p_g_h = parent.get_bounding_rect()
    n_x, n_y, n_w, n_h, n_g_x, n_g_y, n_g_w, n_g_h = node.get_bounding_rect()

    print("-" * 120)
    print('Connecting Parent {} to Node {} via {}.'.format(parent, node, direction))
    print('PX: {}\tPY: {}\tPW: {}\tPH: {}\tPGW: {}\tPGH: {}'.format(p_x, p_y,
                                                                    p_w, p_h,
                                                                    p_g_w,
                                                                    p_g_h))
    print('NX: {}\tNY: {}\tNW: {}\tNH: {}\tNGW: {}\tNGH: {}'.format(n_x, n_y,
                                                                    n_w, n_h,
                                                                    n_g_w,
                                                                    n_g_h))

    x = 0
    y = 0
    spacing_x = 0
    spacing_y = 0

    if parent_to_node:
        # We invert direction because we are connecting the parent into the
        # node and not the opposite.
        # That is because we need less moving pieces by traversing the tree
        # in a depth first method.
        inv_dir = invert_direction[direction]

        x = n_x
        y = n_y

        if 'n' in inv_dir or 's' in inv_dir:
            if 'e' in inv_dir:
                spacing_x = n_g_w - n_w if n_x == 0 else 0
                x += n_w + spacing_x + min_spacing
            elif 'w' in inv_dir:
                spacing_x = n_g_w - n_w if n_x != 0 else 0
                x += -min_spacing - spacing_x - p_w
            else:
                x += n_w / 2.0 - p_w / 2.0

            if 'n' in inv_dir:
                spacing_y = n_g_h - n_h if n_y != n_g_y else 0
                y += -min_spacing - spacing_y - p_h
            elif 's' in inv_dir:
                spacing_y = n_g_h - n_h if n_y == 0 else 0
                y += n_h + min_spacing + spacing_y
        elif 'e' in inv_dir:
            spacing_x = n_g_w - n_w if n_x == 0 else 0
            x += n_w + spacing_x + min_spacing
            y += n_h / 2.0 - p_h / 2.0
        elif 'w' in inv_dir:
            spacing_x = n_g_w - n_w if n_x != 0 else 0
            x += -min_spacing - spacing_x - p_w
            y += n_h / 2.0 - p_h / 2.0
    else:
        x = p_x
        y = p_y
        if 'n' in direction or 's' in direction:
            if 'e' in direction:
                x += p_w + min_spacing
            elif 'w' in direction:
                x += -min_spacing - n_w
            else:
                x += p_w / 2.0 - n_w / 2.0  # ?

            if 'n' in direction:
                y = n_y - min_spacing - spacing_y - p_h
                # TODO: check n_y vs p_y here?
            elif 's' in direction:
                y += p_h + min_spacing
        else:
            if 'e' in direction:
                x += p_w + min_spacing
                y += p_h / 2.0 - n_h / 2.0
            elif 'w' in direction:
                x += -min_spacing - n_w
                y += p_h / 2.0 - n_h / 2.0

    return x, y

def layout(scene, root, parent, min_spacing=30, visited=[]):
    connections = dict()
    if parent in visited:
        return
    visited.append(parent)
    for node in parent.walk_depth_first():
        try:
            dir = parent.get_direction_to_child(node)
        except ValueError:
            continue
        child = list(node.walk_depth_first())
        if len(child) > 1:
            layout(scene, root, node, min_spacing, visited=visited)
        connections[dir] = node
        # print('Parent: {} connected to Node: {} via {} anchor'.format(parent, node, dir))

    for dir, node in connections.items():
        if parent.positioned:
            x, y = calculate_position(parent, node, dir, min_spacing, parent_to_node=False)
            node.shape.setPos(x, y)
        else:
            x, y = calculate_position(parent, node, dir, min_spacing, parent_to_node=True)
            parent.shape.setPos(x, y)
            parent.positioned = True
        for item in node.get_nodes():
            parent.group.addToGroup(item.shape)
        parent.group.addToGroup(node.shape)
        if parent.group not in scene.items():
            scene.addItem(parent.group)

def connect_widgets(scene, parent, visited=[]):
    if parent in visited:
        return
    visited.append(parent)

    pen = QtGui.QPen(QtGui.QColor("deepskyblue"), 3)
    pen.setCapStyle(QtCore.Qt.FlatCap)
    pen.setJoinStyle(QtCore.Qt.RoundJoin)

    connections = dict()
    for node in parent.walk_depth_first():
        try:
            dir = parent.get_direction_to_child(node)
        except ValueError:
            continue
        child = list(node.walk_depth_first())
        if len(child) > 1:
            connect_widgets(scene, node, visited=visited)
        connections[dir] = node

    for dir, node in connections.items():
        p_w = parent.widget.width()
        p_h = parent.widget.height()

        n_w = node.widget.width()
        n_h = node.widget.height()

        l_x1 = parent.shape.pos().x()
        l_y1 = parent.shape.pos().y()
        l_x2 = node.shape.pos().x()
        l_y2 = node.shape.pos().y()

        if dir == 'n':
            l_x1 += p_w/2.0
            l_y1 += 0.0
            l_x2 += n_w/2.0
            l_y2 += n_h
        elif dir == 's':
            l_x1 += p_w/2.0
            l_y1 += p_h
            l_x2 += n_w/2.0
            l_y2 += 0.0
        elif dir == 'e':
            l_x1 += p_w
            l_y1 += p_h/2.0
            l_x2 += 0.0
            l_y2 += n_h/2.0
        elif dir == 'w':
            l_x1 += 0.0
            l_y1 += p_h/2.0
            l_x2 += n_w
            l_y2 += n_h/2.0
        elif dir == 'nw':
            l_x1 += 0
            l_y1 += 0
            l_x2 += n_w
            l_y2 += n_h
        elif dir == 'ne':
            l_x1 += p_w
            l_y1 += 0
            l_x2 += 0
            l_y2 += n_h
        elif dir == 'sw':
            l_x1 += 0
            l_y1 += p_h
            l_x2 += n_w
            l_y2 += 0
        elif dir == 'se':
            l_x1 += p_w
            l_y1 += p_h
            l_x2 += 0
            l_y2 += 0

        scene.addLine(
            QtCore.QLineF(
                l_x1,
                l_y1,
                l_x2,
                l_y2
            ),
            pen
        )

def validate(scene, shapes):
    for idx, shape in shapes.items():
        collisions = scene.collidingItems(shape)
        if len(collisions) > 0:
            for c in collisions:
                print('Item: ', idx, ' bumped with: ', c)#c.widget().text())
            return False
    return True

def remove_groups(scene, parent, visited=[]):
    for _, nodes in parent.connections.items():
        for node in nodes:
            if node in visited:
                continue
            visited.append(node)
            remove_groups(scene, node, visited)
    scene.destroyItemGroup(parent.group)


def main(app, connections, sizes):
    registry = qtpynodeeditor.DataModelRegistry()
    scene = qtpynodeeditor.FlowScene(registry=registry)

    view = qtpynodeeditor.FlowView(scene)
    view.setWindowTitle("Style example")
    view.resize(800, 600)

    shapes = {
        idx: QtWidgets.QLabel(f'{idx}: {connections[idx]}')
        for idx in range(len(sizes))
    }

    for size, (idx, shape) in zip(sizes, shapes.items()):
        # shape.setFixedSize(size[0] * 10, size[1] * 10)
        # shape.setStyleSheet(
        #     "border: 2px solid white; border-radius: 5px; background: transparent; color: red;")

        proxy = scene.addWidget(shape)
        shapes[idx] = proxy
        proxy.setPos(0, 0)

    root = build_tree(shapes, connections)

    layout(scene, root, root)
    remove_groups(scene, root)
    validate(scene, shapes)
    connect_widgets(scene, root)

    return scene, view, root

def save_image(scene, view, fn, bg=QtCore.Qt.black):
    area = scene.itemsBoundingRect()
    image = QtGui.QImage(area.width(), area.height(), QtGui.QImage.Format_ARGB32_Premultiplied)
    image.fill(bg)
    painter = QtGui.QPainter(image)
    scene.render(painter, QtCore.QRectF(image.rect()), area)
    painter.end()
    image.save(fn)
    print(f'saved image to {fn}')

def test_1():
    conns = {
        0: {'w': 1, 'e': 2, 'n': 3, 's': 4},
        1: {},
        2: {},
        3: {},
        4: {}
    }

    # node = scene.create_node(MyDataModel)
    sizes = [(12, 6), (3, 3), (9, 3), (3, 3), (3, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    # sizes = [(21, 3), (3, 3), (3, 6), (3, 3), (7, 3), (3, 6), (3, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    sizes = [(12, 3), (21, 3), (12, 6), (3, 3), (9, 3)]
    return conns, sizes

def test_11():
    conns = {
        0: {'w': 1},
        1: {'n': 2, 's': 3},
        2: {},
        3: {}
    }

    # node = scene.create_node(MyDataModel)
    sizes = [(3, 3), (12, 6), (3, 3), (9, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    # sizes = [(21, 3), (3, 3), (3, 6), (3, 3), (7, 3), (3, 6), (3, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    # sizes = [(12, 3), (21, 3), (12, 6), (3, 3), (9, 3), (3, 6), (9, 3)]
    return conns, sizes

def test_12():
    conns = {
        0: {'s': 1},
        1: {'w': 2},
        # 2: {}
        2: {'w': 3},
        3: {}
    }

    # node = scene.create_node(MyDataModel)
    sizes = [(3, 3), (3, 3), (3, 3), (3, 3)]
    # sizes = [(3, 3), (3, 3), (3, 3), (3, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    # sizes = [(21, 3), (3, 3), (3, 6), (3, 3), (7, 3), (3, 6), (3, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    # sizes = [(12, 3), (21, 3), (12, 6), (3, 3), (9, 3), (3, 6), (9, 3)]
    return conns, sizes

def test_2():
    conns = {
        0: {'n': 1},
        1: {'e': 2},
        2: {'n': 3, 's': 4},
        3: {},
        4: {}
    }

    # node = scene.create_node(MyDataModel)
    # sizes = [(3, 3),(3, 3),(3, 3),(3, 3),(3, 3)]
    sizes = [(12, 3), (3, 3), (12, 6), (3, 3), (9, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    # sizes = [(21, 3), (3, 3), (3, 6), (3, 3), (7, 3), (3, 6), (3, 3)]
    # sizes = [(12, 3), (3, 3), (3, 6), (3, 3), (9, 3), (3, 6), (3, 3)]
    # sizes = [(12, 3), (21, 3), (12, 6), (3, 3), (9, 3), (3, 6), (9, 3)]
    return conns, sizes

def test_square():
    conns = {
        0: {'s': 1},
        1: {'w': 2},
        2: {'s': 3},
        3: {'e': 4},
        4: {}
    }
    sizes = [(3, 3),(3, 3),(3, 3),(3, 3), (3, 3)]
    return conns, sizes

def test_ken():
    conns = {
        0: {'n': 1},
        1: {'e': 2},
        2: {'s': 3},
        3: {'w': 4},
        4: {'n': 5},
        5: {}
    }
    sizes = [(3, 3),(3, 3),(3, 3),(3, 3), (3, 3), (3, 3)]
    return conns, sizes

def test_ken2():
    conns = {
        0: {'e': 1},
        1: {'s': 2},
        2: {'w': 3},
        3: {'s': 4},
        4: {'e': 5},
        5: {}
    }
    sizes = [(3, 3),(3, 3),(3, 3),(3, 3), (3, 3), (3, 3)]
    return conns, sizes

def test_loop_connections():
    conns = {
        0: {'n': 1},
        1: {'e': 2},
        2: {'n': 3},
        3: {'w': 4},
        4: {'s': 1}
    }
    sizes = [(3, 3),(3, 3),(3, 3),(3, 3), (3, 3)]
    return conns, sizes


def test_intercardinal():
    conns = {
        0: {'ne': 1},
        1: {'se': 2},
        2: {'sw': 3},
        3: {'nw': 4},
        4: {},
    }
    sizes = [(3, 3),(3, 3),(3, 3),(3, 3),(3, 3)]
    return conns, sizes



def closest_point_to(target: QtCore.QPointF,
                     source_path: QtGui.QPainterPath) -> QtCore.QPointF:
    '''
    Returns the closest element (position) in source_path to target, using
    QPoint.manhattanLength() to determine the distances.
    '''
    assert not source_path.isEmpty()

    shortest_distance = QtCore.QPointF(source_path.elementAt(0)) - target
    shortest_length = shortest_distance.manhattanLength()

    for i in range(1, source_path.elementCount()):
        distance = QtCore.QPointF(source_path.elementAt(i)) - target
        length = distance.manhattanLength()
        if length < shortest_length:
            shortest_distance = QtCore.QPointF(source_path.elementAt(i))
            shortest_length = length
    return shortest_distance


def hit(projectile_path: QtGui.QPainterPath,
        scene: QtWidgets.QGraphicsScene,
        ) -> QtCore.QPointF:
    '''
    If projectile_path intersects with any items in scene, returns the position
    of the intersection.
    '''
    items_in_path = scene.items(projectile_path, QtCore.Qt.IntersectsItemBoundingRect)
    if not items_in_path:
        return None

    projectile_start_pos = QtCore.QPointF(projectile_path.elementAt(0))
    shortest_distance = 1e99
    closest = None
    for item in items_in_path:
        distance_as_point = item.pos() - projectile_start_pos
        distance = abs(distance_as_point.x() + distance_as_point.y())
        if distance < shortest_distance:
            shortest_distance = distance
            closest = item

    target_shape = QtGui.QPainterPath(closest.mapToScene(closest.shape()))

    # QLineF has normalVector(), which is useful for extending our path to a
    # rectangle.  The path needs to be a rectangle, as
    # QPainterPath.intersected() only accounts for intersections between fill
    # areas, which projectile_path doesn't have.
    path_as_line = QtCore.QLineF(projectile_start_pos,
                                 QtCore.QPointF(projectile_path.elementAt(1))
                                 )

    # Extend the first point in the path out by 1 pixel.
    start_edge = path_as_line.normalVector()
    start_edge.setLength(1)

    # Swap the points in the line so the normal vector is at the other end of
    # the line.
    path_as_line.setPoints(path_as_line.p2(), path_as_line.p1())
    end_edge = path_as_line.normalVector()

    # The end point is currently pointing the wrong way move it to face the
    # same direction as start_edge.
    end_edge.setLength(-1)

    # Now we can create a rectangle from our edges.
    rect_path = QtGui.QPainterPath(start_edge.p1())
    rect_path.lineTo(start_edge.p2())
    rect_path.lineTo(end_edge.p2())
    rect_path.lineTo(end_edge.p1())
    rect_path.lineTo(start_edge.p1())

    # Visualize the rectangle that we created.
    scene.addPath(rect_path, QtGui.QPen(QtGui.QBrush(QtCore.Qt.blue), 2))

    # Visualize the intersection of the rectangle with the item.
    scene.addPath(target_shape.intersected(rect_path),
                  QtGui.QPen(QtGui.QBrush(QtCore.Qt.cyan), 2))

    # The hit position will be the element (point) of the rectangle that is the
    # closest to where the projectile was fired from.
    return closest_point_to(projectile_start_pos,
                            target_shape.intersected(rect_path))


def intersection_test(scene):
    projectile_path = QtGui.QPainterPath()
    projectile_path.moveTo(100, 100)
    projectile_path.lineTo(200, 0)
    projectile_path.lineTo(100, 300)

    hit_pos = hit(projectile_path, scene)
    if hit_pos:
        print(hit_pos, hit_pos.x, hit_pos.y)

        hit_x, hit_y = hit_pos.x(), hit_pos.y()
        scene.addEllipse(hit_x - 2,
                         hit_y - 2, 4, 4,
                         QtGui.QPen(QtCore.Qt.red))

    scene.addPath(projectile_path, QtGui.QPen(QtCore.Qt.DashLine))
    scene.addText("start").setPos(180, 150)
    scene.addText("end").setPos(20, 0)


if __name__ == '__main__':
    logging.basicConfig(level='DEBUG')
    app = QtWidgets.QApplication([])

    conns, sizes = test_ken()
    # conns, sizes = test_loop_connections()
    # scene, view, nodes = main(app, conns, sizes)

    tests = {'test_1': test_1}

    for test_name, test in tests.items():
        conns, sizes = test()
        scene, view, nodes = main(app, conns, sizes)
        intersection_test(scene)
        save_image(scene, view, fn=f"output/{test_name}.png")

    view.show()
    app.exec_()
