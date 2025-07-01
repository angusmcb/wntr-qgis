from __future__ import annotations

import contextlib
import enum
import math
import typing
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsLayerTreeLayer,
    QgsLayerTreeNode,
    QgsProcessingAlgRunnerTask,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingOutputLayerDefinition,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
    QgsSettings,
    QgsTask,
)
from qgis.gui import QgisInterface, QgsLayerTreeViewIndicator, QgsProjectionSelectionDialog
from qgis.PyQt.QtCore import QCoreApplication, QLocale, QObject, QSettings, QTranslator, pyqtSlot

# from qgis.processing import execAlgorithmDialog for qgis 3.40 onwards
from qgis.PyQt.QtGui import QIcon, QPainter, QPixmap
from qgis.PyQt.QtWidgets import (
    QAction,
    QActionGroup,
    QFileDialog,
    QMenu,
    QPushButton,
    QToolButton,
    QWidget,
)
from qgis.utils import iface

import wntrqgis
import wntrqgis.expressions
from wntrqgis.dependency_management import WntrInstaller
from wntrqgis.elements import (
    FlowUnit,
    HeadlossFormula,
    ModelLayer,
    ResultLayer,
)
from wntrqgis.i18n import tr
from wntrqgis.settings import ProjectSettings, SettingKey
from wntrqgis.wntrqgis_processing.provider import Provider

MESSAGE_CATEGORY = "WNTR-QGIS"
WNTR_SETTING_VERSION = "wntrqgis/version"

iface = typing.cast(QgisInterface, iface)


class _InstallStatus(enum.Enum):
    NO_CHANGE = enum.auto()
    FRESH_INSTALL = enum.auto()
    UPGRADE = enum.auto()


class Plugin:
    TESTING = False

    def __init__(self) -> None:
        # setup_logger("wntrqgis")

        # initialize locale
        # locale, file_path = setup_translation()
        # if file_path:
        #     self.translator = QTranslator()
        #     self.translator.load(file_path)
        #     # noinspection PyCallByClass
        #     # QCoreApplication.installTranslator(self.translator)
        # else:
        #     pass

        self.actions: dict[str, typing.Any] = {}
        self.init_translation()
        self.menu = tr("Water Network Tools for Resilience")

        s = QgsSettings()
        oldversion = s.value(WNTR_SETTING_VERSION, None)
        s.setValue(WNTR_SETTING_VERSION, wntrqgis.__version__)
        if oldversion is None:
            self._install_status = _InstallStatus.FRESH_INSTALL
        elif oldversion != wntrqgis.__version__:
            self._install_status = _InstallStatus.UPGRADE
        else:
            self._install_status = _InstallStatus.NO_CHANGE

        with contextlib.suppress(ModuleNotFoundError, AttributeError):
            import console

            console.console_sci._init_statements.extend(  # noqa SLF001
                [
                    "import wntrqgis",
                    """
try:
    import wntr
except ModuleNotFoundError:
    pass
""",
                ]
            )

    def init_translation(self):
        qgis_locale = QLocale(QSettings().value("locale/userLocale"))
        locale_path = str(Path(__file__).parent / "resources" / "i18n")
        self.translator = QTranslator()
        self.translator.load(qgis_locale, "", "", locale_path)
        QCoreApplication.installTranslator(self.translator)

    def add_action(
        self,
        key: str,
        icon: QIcon | str | None,
        text: str,
        callback: typing.Callable,
        *,
        enabled_flag: bool = True,
        add_to_menu: bool = True,
        add_to_toolbar: bool = False,
        status_tip: str | None = None,
        whats_this: str | None = None,
        parent: QWidget | None = None,
    ):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.

        :param text: Text that should be shown in menu items for this action.

        :param callback: Function to be called when the action is triggered.

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.

        :param parent: Parent widget for the new action. Defaults None.

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon)
        action = QAction(icon, text, parent)
        # noinspection PyUnresolvedReferences
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            iface.addToolBarIcon(action)

        if add_to_menu:
            iface.addPluginToMenu(self.menu, action)

        self.actions[key] = action

        return action

    def initProcessing(self):  # noqa N802
        self.provider = Provider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self) -> None:  # noqa N802
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        self.add_action(
            "template_layers",
            IconWithLogo(":images/themes/default/mActionFileNew.svg"),
            text=tr("Create Template Memory Layers"),
            callback=self.create_template_layers,
            parent=iface.mainWindow(),
        )

        self.add_action(
            "create_template_geopackage",
            IconWithLogo(":images/themes/default/mGeoPackage.svg"),
            text=tr("Create Template Geopackage"),
            callback=self.create_template_geopackage,
            parent=iface.mainWindow(),
        )

        template_button = QToolButton()

        template_menu = QMenu(template_button)
        template_menu.addAction(self.actions["template_layers"])
        template_menu.addAction(self.actions["create_template_geopackage"])

        template_button.setMenu(template_menu)
        template_button.setDefaultAction(self.actions["template_layers"])
        template_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        self.actions["template_layers_menu_widget"] = iface.addToolBarWidget(template_button)

        self.add_action(
            "load_inp",
            IconWithLogo(":images/themes/default/mActionFileOpen.svg"),
            text=tr("Load from .inp file"),
            callback=self.load_inp_file,
            parent=iface.mainWindow(),
            add_to_toolbar=True,
        )
        self.add_action(
            "run_simulation",
            IconWithLogo("wntrqgis:run.svg"),
            text=tr("Run Simulation"),
            callback=self.run_simulation,
            parent=iface.mainWindow(),
        )
        self.add_action(
            "settings",
            "",
            text=tr("Change layers..."),
            callback=self.open_settings,
            parent=iface.mainWindow(),
            add_to_menu=False,
        )

        run_button = QToolButton()

        run_menu = QMenu(run_button)
        run_menu.addAction(self.actions["run_simulation"])
        run_menu.addAction(self.actions["settings"])
        run_menu.addMenu(SettingMenu(tr("Headloss Formula"), run_menu, SettingKey.HEADLOSS_FORMULA))
        run_menu.addMenu(SettingMenu(tr("Units"), run_menu, SettingKey.FLOW_UNITS))
        run_menu.addMenu(DurationSettingMenu(tr("Duration (hours)"), run_menu))

        run_button.setMenu(run_menu)
        run_button.setDefaultAction(self.actions["run_simulation"])
        run_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

        self.actions["run_menu_widget"] = iface.addToolBarWidget(run_button)

        self.add_action(
            "load_example",
            "",
            text=tr("Load Example"),
            callback=self.load_example,
            parent=iface.mainWindow(),
            add_to_toolbar=False,
        )

        self._indicator_registry = IndicatorRegistry()

        self.warm_up_wntr()

        self.initProcessing()

        self._add_icons_to_menu()

    def _add_icons_to_menu(self) -> None:
        for action in iface.pluginMenu().actions():
            if action.text() != self.menu:
                continue
            action.setIcon(QIcon("wntrqgis:logo.png"))

    def warm_up_wntr(self):
        """wntr is slow to load so start warming it up now !"""
        self._load_wntr_task = QgsTask.fromFunction(
            "Set up wntr-qgis",
            import_wntr,
            on_finished=self.install_wntr_if_none,
            flags=QgsTask.Hidden | QgsTask.Silent,
        )
        QgsApplication.taskManager().addTask(self._load_wntr_task)
        if self.TESTING:
            assert self._load_wntr_task.waitForFinished()  # noqa: S101

    def install_wntr_if_none(self, exception, value=None):  # noqa: ARG002
        if exception:
            self._install_wntr_task = QgsTask.fromFunction(
                tr("Installing WNTR"),
                lambda _: WntrInstaller.install_wntr(),
                on_finished=self.show_welcome_message,
                flags=QgsTask.Silent,
            )
            QgsApplication.taskManager().addTask(self._install_wntr_task)
            if self.TESTING:
                assert self._install_wntr_task.waitForFinished()  # noqa: S101
        else:
            self.show_welcome_message(None, None)

    # exception and value are required for on_finished to work
    def show_welcome_message(self, exception, value=None):  # noqa: ARG002
        if exception:
            iface.messageBar().pushMessage(
                tr("Failed to install WNTR. Please check your internet connection."),
                level=Qgis.MessageLevel.Critical,
            )
            return

        if self._install_status in [_InstallStatus.FRESH_INSTALL, _InstallStatus.UPGRADE]:
            msg = (
                tr("WNTR QGIS installed successfully")
                if self._install_status == _InstallStatus.FRESH_INSTALL
                else tr("WNTR QGIS upgraded successfully")
            )

            message_item = iface.messageBar().createMessage(
                msg,
                tr("Load an example to try me out"),
            )

            example_button = QPushButton(message_item)
            example_button.setText(tr("Load Example"))
            example_button.clicked.connect(self.load_example)
            example_button.clicked.connect(message_item.dismiss)

            message_item.layout().addWidget(example_button)
            message_item.setLevel(Qgis.MessageLevel.Info)

            iface.messageBar().pushItem(message_item)

    def onClosePlugin(self) -> None:  # noqa N802
        """Cleanup necessary items here when plugin dockwidget is closed"""

    def unload(self) -> None:
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions.values():
            iface.removePluginMenu(self.menu, action)
            iface.removeToolBarIcon(action)

        # teardown_logger("wntrqgis")

        QgsApplication.processingRegistry().removeProvider(self.provider)

        self._indicator_registry.destroy()

    def run_alg_async(self, algorithm_name, parameters, on_finish=None, success_message: str | None = None):
        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())
        feedback = WqProcessingFeedback()
        algorithm = QgsApplication.instance().processingRegistry().algorithmById(algorithm_name)

        def task_finished(successful, results):
            nonlocal context
            nonlocal feedback
            nonlocal algorithm
            if not successful:
                iface.messageBar().pushMessage(
                    title=tr("Error"),
                    text=feedback.errors[0],
                    showMore=feedback.textLog(),
                    level=Qgis.MessageLevel.Critical,
                    duration=0,
                )

                QgsApplication.messageLog().logMessage(
                    feedback.errors[0] + "\n" + feedback.textLog(),
                    MESSAGE_CATEGORY,
                    Qgis.MessageLevel.Critical,
                )
                return

            import processing

            processing.handleAlgorithmResults(algorithm, context, feedback, results)

            if on_finish:
                on_finish()

            if success_message:
                level = Qgis.MessageLevel.Warning if feedback.warnings else Qgis.MessageLevel.Success
                title = tr("Analysed with Warnings") if feedback.warnings else tr("Success")
                iface.messageBar().pushMessage(
                    title=title,
                    text=success_message,
                    showMore=feedback.textLog(),
                    level=level,
                    duration=0,
                )

        task = QgsProcessingAlgRunnerTask(algorithm, parameters, context, feedback)
        task.executed.connect(task_finished)

        QgsApplication.taskManager().addTask(task)
        if self.TESTING:
            assert task.waitForFinished()  # noqa: S101

    def create_template_layers(self) -> None:
        parameters = {"CRS": QgsProject.instance().crs(), **self._empty_model_layer_dict()}
        self.run_alg_async("wntr:templatelayers", parameters)

    def load_inp_file(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            None, tr("Choose Input File"), QSettings().value("UI/lastProjectDir"), tr("EPANET INP File") + " (*.inp)"
        )
        if not filepath:
            return

        crs_selector = QgsProjectionSelectionDialog(iface.mainWindow())
        crs_selector.setCrs(QgsProject.instance().crs())
        crs_selector.showNoCrsForLayerMessage()
        if not crs_selector.exec():
            return
        crs = crs_selector.crs()

        parameters = {"INPUT": str(filepath), "CRS": crs, **self._empty_model_layer_dict()}
        self.run_alg_async(
            "wntr:importinp",
            parameters,
            success_message=tr("Loaded .inp file"),
        )

    def load_example(self) -> None:
        network_crs = QgsCoordinateReferenceSystem("EPSG:3089")
        transform_context = QgsProject.instance().transformContext()
        transform_string = (
            "+proj=pipeline +step +inv +proj=webmerc +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +ellps=WGS84 +step +inv"
            " +proj=hgridshift +grids=us_noaa_kyhpgn.tif +step"
            " +proj=lcc +lat_0=36.3333333333333 +lon_0=-85.75 +lat_1=37.0833333333333 +lat_2=38.6666666666667"
            " +x_0=1500000 +y_0=999999.9998984 +ellps=GRS80 +step"
            " +proj=unitconvert +xy_in=m +xy_out=us-ft"
        )
        transform_context.addCoordinateOperation(
            QgsCoordinateReferenceSystem("EPSG:3857"), network_crs, transform_string, False
        )
        QgsProject.instance().setTransformContext(transform_context)

        parameters = {"INPUT": wntrqgis.examples["KY10"], "CRS": network_crs, **self._empty_model_layer_dict()}
        self.run_alg_async(
            "wntr:importinp",
            parameters,
            on_finish=self.load_osm,
            success_message=tr("Example loaded with Open Street Map background"),
        )

    def open_settings(self) -> None:
        import processing

        processing.execAlgorithmDialog("wntr:run")  # type: ignore

    def run_simulation(self) -> None:
        project_settings = ProjectSettings(QgsProject.instance())
        saved_layers = project_settings.get(SettingKey.MODEL_LAYERS, {})
        input_layers = {layer_type.name: saved_layers.get(layer_type.name) for layer_type in ModelLayer}
        result_layers = {layer.results_name: self._temporary_processing_output() for layer in ResultLayer}
        flow_units = project_settings.get(SettingKey.FLOW_UNITS, FlowUnit.LPS)
        flow_unit_id = list(FlowUnit).index(flow_units)
        headloss_formula = project_settings.get(SettingKey.HEADLOSS_FORMULA, HeadlossFormula.HAZEN_WILLIAMS)
        headloss_formula_id = list(HeadlossFormula).index(headloss_formula)
        duration = project_settings.get(SettingKey.SIMULATION_DURATION, 0)
        parameters = {
            "UNITS": flow_unit_id,
            "HEADLOSS_FORMULA": headloss_formula_id,
            "DURATION": duration,
            **result_layers,
            **input_layers,
        }

        success_message = tr("Analysed using units '{units}' and headloss formula '{headloss_formula}'").format(
            units=flow_units.friendly_name,
            headloss_formula=headloss_formula.friendly_name,
        )

        self.run_alg_async(
            "wntr:run",
            parameters,
            success_message=success_message,
        )

    def create_template_geopackage(self):
        geopackage_path, _ = QFileDialog.getSaveFileName(
            iface.mainWindow(),
            tr("Save Geopackage"),
            QSettings().value("UI/lastProjectDir"),
            tr("Geopackage") + " (*.gpkg)",
        )
        if not geopackage_path:
            return

        params = {"CRS": None, **self._empty_model_layer_dict(geopackage_path)}

        self.run_alg_async("wntr:templatelayers", params)

    def _geopackage_processing_output(self, path, name):
        return QgsProcessingOutputLayerDefinition(f"ogr:dbname='{path}' table='{name}' (geom)", QgsProject.instance())

    def _temporary_processing_output(self):
        return QgsProcessingOutputLayerDefinition("TEMPORARY_OUTPUT", QgsProject.instance())

    def _empty_model_layer_dict(self, path=None):
        if path:
            return {layer.value: self._geopackage_processing_output(path, layer.value.lower()) for layer in ModelLayer}
        return {layer.value: self._temporary_processing_output() for layer in ModelLayer}

    def finish_loading_example_ky10(self):
        # Doesn't work due to this:
        # https://github.com/qgis/QGIS/issues/27139
        view_box = QgsRectangle(5765000, 3830000, 5780000, 3838000)

        transform = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem("EPSG:3089"), QgsProject.instance().crs(), QgsProject.instance()
        )

        view_box = transform.transform(view_box)

        iface.mapCanvas().setExtent(view_box)

        iface.mapCanvas().refresh()
        self.load_osm()

    def load_osm(self):
        root = QgsProject.instance().layerTreeRoot()
        tms = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0"
        title = tr("OpenStreetMap")
        layer = QgsRasterLayer(tms, title, "wms")
        layer.setOpacity(0.5)
        QgsProject.instance().addMapLayer(layer, False)
        root.insertChildNode(len(root.children()), QgsLayerTreeLayer(layer))


class WqProcessingFeedback(QgsProcessingFeedback):
    def __init__(self, logFeedback: bool = True):  # noqa
        self.errors: list[str] = []
        self.warnings: list[str] = []
        super().__init__(logFeedback)

    def reportError(self, error: str | None, fatalError: bool = False):  # noqa N802
        if error:
            self.errors.append(error)

        super().reportError(error, fatalError)

    def pushWarning(self, warning: str | None):  # noqa N802
        if warning:
            self.warnings.append(warning)

        super().pushWarning(warning)


def import_wntr(task: QgsTask):  # noqa: ARG001
    """Pre-import wntr to speed up loading"""
    import wntr  # type: ignore

    if not Path(wntr.__file__).exists():
        msg = "File missing - probably due to plugin upgrade"
        raise ImportError(msg)


class IconWithLogo(QIcon):
    _logo = QPixmap("wntrqgis:logo.png")

    def __init__(self, icon_path: str):
        result_pixmap = QIcon(icon_path).pixmap(256, 256)
        painter = QPainter(result_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(128, 128, 128, 128, self._logo)
        painter.end()

        super().__init__(result_pixmap)


class IndicatorRegistry(QObject):
    """Registry for layer tree indicators"""

    def __init__(self) -> None:
        super().__init__()

        self._layer_ids: dict[ModelLayer, str] = {}
        self._indicators = {layer: ModelLayerIndicator(self, layer) for layer in ModelLayer}

        root = QgsProject.instance().layerTreeRoot()
        root.addedChildren.connect(self.layer_tree_layer_added)
        root.willRemoveChildren.connect(self.layer_tree_layer_will_be_removed)

        QgsProject.instance().customVariablesChanged.connect(self.update_layer_ids)

        self.update_layer_ids()

    def destroy(self) -> None:
        """Self destruct mechanism"""
        for layer_type in ModelLayer:
            old_id = self._layer_ids.get(layer_type)
            if not old_id:
                continue

            layer_tree_layer = QgsProject.instance().layerTreeRoot().findLayer(old_id)

            if layer_tree_layer:
                indicator = self._indicators[layer_type]
                iface.layerTreeView().removeIndicator(layer_tree_layer, indicator)

        self.deleteLater()

    @pyqtSlot(QgsLayerTreeNode, int, int)
    def layer_tree_layer_added(
        self,
        layer_tree: QgsLayerTreeNode,
        indexFrom: int,  # noqa: N803
        indexTo: int,  # noqa: N803
    ) -> None:
        """Receive layer tree layers added and attach indicator to them if indicator exists."""

        layer_tree_nodes = layer_tree.children()[indexFrom : indexTo + 1]

        for layer_tree_node in layer_tree_nodes:
            try:
                layer_id = layer_tree_node.layerId()
            except AttributeError:  # Not a layer node
                continue

            if layer_id not in self._layer_ids.values():
                continue

            model_layer = next(key for key, value in self._layer_ids.items() if value == layer_id)

            indicator = self._indicators[model_layer]

            iface.layerTreeView().addIndicator(layer_tree_node, indicator)

    @pyqtSlot(QgsLayerTreeNode, int, int)
    def layer_tree_layer_will_be_removed(
        self,
        layer_tree: QgsLayerTreeNode,
        indexFrom: int,  # noqa: N803
        indexTo: int,  # noqa: N803
    ) -> None:
        """Receive layer tree layers added and attach indicator to them if indicator exists."""

        layer_tree_view = iface.layerTreeView()
        layer_tree_nodes = layer_tree.children()[indexFrom : indexTo + 1]

        for layer_tree_node in layer_tree_nodes:
            for indicator in layer_tree_view.indicators(layer_tree_node):
                if isinstance(indicator, ModelLayerIndicator):
                    layer_tree_view.removeIndicator(layer_tree_node, indicator)

    @pyqtSlot()
    def update_layer_ids(self) -> None:
        """Update the layer ids in the registry based on project settings."""
        new_layer_ids: dict[ModelLayer, str] = {}
        for layer, layer_id in ProjectSettings().get(SettingKey.MODEL_LAYERS, {}).items():
            try:
                new_layer_ids[ModelLayer[layer]] = layer_id
            except KeyError:
                continue

        if new_layer_ids == self._layer_ids:
            return

        for layer_type in ModelLayer:
            old_id = self._layer_ids.get(layer_type)
            new_id = new_layer_ids.get(layer_type)

            if old_id == new_id:
                continue

            indicator = self._indicators[layer_type]
            root = QgsProject.instance().layerTreeRoot()

            if old_id:
                layer_tree_layer = root.findLayer(old_id)
                if layer_tree_layer:
                    iface.layerTreeView().removeIndicator(layer_tree_layer, indicator)

            if new_id:
                layer_tree_layer = root.findLayer(new_id)
                if layer_tree_layer:
                    iface.layerTreeView().addIndicator(layer_tree_layer, indicator)

        self._layer_ids = new_layer_ids


class ModelLayerIndicator(QgsLayerTreeViewIndicator):
    _icon = QIcon("wntrqgis:logo.png")

    def __init__(self, parent: QObject, layer_type: ModelLayer):
        super().__init__(parent)

        self.setIcon(self._icon)
        self.setToolTip(layer_type.friendly_name)


class SettingMenu(QMenu):
    def __init__(self, title: str | None = None, parent: QWidget | None = None, setting: SettingKey | None = None):
        super().__init__(title, parent)

        self.action_group = QActionGroup(self)
        self.action_group.triggered.connect(lambda action: ProjectSettings().set(setting, action.data()))  # type: ignore
        self.actions = {}  # type: ignore
        self.setting_key = setting

        self.setup_actions()

        self.aboutToShow.connect(self.update_checked)

    def setup_actions(self):
        for option in self.setting_key.expected_type:
            self.setup_action(option, option.friendly_name)

    def setup_action(self, option, option_name: str):
        action = QAction(option_name, self.action_group, checkable=True)
        action.setData(option)
        self.actions[option] = action
        self.addAction(action)

    def update_checked(self):
        current_setting = ProjectSettings().get(self.setting_key, next(iter(self.setting_key.expected_type)))
        self.actions[current_setting].setChecked(True)


class DurationSettingMenu(SettingMenu):
    def __init__(self, title=None, parent=None):
        super().__init__(title, parent, SettingKey.SIMULATION_DURATION)

    def setup_actions(self):
        self.setup_action(0, tr("Single period simulation"))

        for hour in range(1, 25):
            self.setup_action(hour, tr("%n hour(s)", "", hour))

    def update_checked(self):
        current_duration = math.floor(ProjectSettings().get(SettingKey.SIMULATION_DURATION, 0))

        if current_duration not in self.actions:
            self.setup_action(current_duration, tr("%n hour(s)", "", current_duration))

        self.actions[current_duration].setChecked(True)
