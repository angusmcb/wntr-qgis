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
    QgsMessageLog,
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
from qgis.PyQt.QtCore import QCoreApplication, QLocale, QObject, QSettings, QTranslator, pyqtSignal, pyqtSlot

# from qgis.processing import execAlgorithmDialog for qgis 3.40 onwards
from qgis.PyQt.QtGui import QColorConstants, QIcon, QPainter, QPixmap
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
import wntrqgis.resources.icons.resources
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
        icon_path: str,
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

        icon = QIcon(icon_path)
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
            join_pixmap(QPixmap(":images/themes/default/mActionFileNew.svg"), QPixmap(":wntrqgis/logo.svg")),
            text=tr("Create Template Memory Layers"),
            callback=self.create_template_layers,
            parent=iface.mainWindow(),
        )

        self.add_action(
            "create_template_geopackage",
            join_pixmap(QPixmap(":images/themes/default/mGeoPackage.svg"), QPixmap(":wntrqgis/logo.svg")),
            text=tr("Create Template Geopackage"),
            callback=self.create_template_geopackage,
            parent=iface.mainWindow(),
        )

        template_layers_menu = QMenu(iface.mainWindow())
        template_layers_menu.addAction(self.actions["template_layers"])
        template_layers_menu.addAction(self.actions["create_template_geopackage"])

        self.template_layers_button = QToolButton()
        self.template_layers_button.setMenu(template_layers_menu)
        self.template_layers_button.setDefaultAction(self.actions["template_layers"])
        self.template_layers_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        self.actions["template_layers_menu_widget"] = iface.addToolBarWidget(self.template_layers_button)

        self.add_action(
            "load_inp",
            join_pixmap(QPixmap(":images/themes/default/mActionFileOpen.svg"), QPixmap(":wntrqgis/logo.svg")),
            text=tr("Load from .inp file"),
            callback=self.load_inp_file,
            parent=iface.mainWindow(),
            add_to_toolbar=True,
        )
        self.add_action(
            "run_simulation",
            join_pixmap(QPixmap(":wntrqgis/run.svg"), QPixmap(":wntrqgis/logo.svg")),
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

        self.run_menu = QMenu(iface.mainWindow())
        self.run_menu.addAction(self.actions["run_simulation"])
        self.run_menu.addAction(self.actions["settings"])

        headloss_formula_menu = QMenu(tr("Headloss Formula"), iface.mainWindow())
        headloss_formula_group = QActionGroup(headloss_formula_menu)

        self.headloss_formula_actions = {}

        for hlf in HeadlossFormula:
            self.headloss_formula_actions[hlf] = QAction(hlf.friendly_name, headloss_formula_menu, checkable=True)
            self.headloss_formula_actions[hlf].setData(hlf)
            self.headloss_formula_actions[hlf].triggered.connect(lambda _, param=hlf: self.set_headloss_formula(param))
            headloss_formula_menu.addAction(self.headloss_formula_actions[hlf])
            headloss_formula_group.addAction(self.headloss_formula_actions[hlf])
        headloss_formula_group.setExclusive(True)
        headloss_formula_menu.aboutToShow.connect(self.update_headloss_formula_menu)

        self.run_menu.addMenu(headloss_formula_menu)

        units_menu = QMenu(tr("Units"), iface.mainWindow())
        units_group = QActionGroup(units_menu)

        self.units_actions = {}

        for unit in FlowUnit:
            self.units_actions[unit] = QAction(unit.friendly_name, units_menu, checkable=True)
            self.units_actions[unit].setData(unit)
            self.units_actions[unit].triggered.connect(lambda _, param=unit: self.set_units(param))
            units_menu.addAction(self.units_actions[unit])
            units_group.addAction(self.units_actions[unit])
        units_group.setExclusive(True)
        units_menu.aboutToShow.connect(self.update_units_menu)

        self.run_menu.addMenu(units_menu)

        self.duration_menu = QMenu(tr("Duration (hours)"), iface.mainWindow())
        self.duration_group = QActionGroup(self.duration_menu)

        self.duration_actions = {}

        self.duration_actions[0] = QAction(tr("Single period simulation"), self.duration_menu, checkable=True)
        self.duration_actions[0].setData(0)
        self.duration_actions[0].triggered.connect(lambda: self.set_duration(0))
        self.duration_menu.addAction(self.duration_actions[0])
        self.duration_group.addAction(self.duration_actions[0])

        for hours in range(1, 25):
            self.duration_actions[hours] = QAction(tr("%n hour(s)", "", hours), self.duration_menu, checkable=True)
            self.duration_actions[hours].setData(hours)
            self.duration_actions[hours].triggered.connect(lambda _, param=hours: self.set_duration(param))
            self.duration_menu.addAction(self.duration_actions[hours])
            self.duration_group.addAction(self.duration_actions[hours])
        self.duration_group.setExclusive(True)
        self.duration_menu.aboutToShow.connect(self.update_duration_menu)

        self.run_menu.addMenu(self.duration_menu)

        self.run_button = QToolButton()
        self.run_button.setMenu(self.run_menu)
        self.run_button.setDefaultAction(self.actions["run_simulation"])
        self.run_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)

        self.actions["run_menu_widget"] = iface.addToolBarWidget(self.run_button)

        self.add_action(
            "load_example",
            "",
            text=tr("Load Example"),
            callback=self.load_example,
            parent=iface.mainWindow(),
            add_to_toolbar=False,
        )

        self.add_layer_indicators()

        self.tm = QgsApplication.taskManager()
        self.warm_up_wntr()

        self.initProcessing()

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
                "Failed to install WNTR. Please check your internet connection.",
                level=Qgis.MessageLevel.Critical,
            )
            return

        if self._install_status in [_InstallStatus.FRESH_INSTALL, _InstallStatus.UPGRADE]:
            msg = (
                tr("WNTR QGIS installed successfully")
                if self._install_status == _InstallStatus.FRESH_INSTALL
                else tr("WNTR QGIS upgraded successfully")
            )

            self.message_widget = iface.messageBar().createMessage(
                msg,
                tr("Load an example to try me out"),
            )

            example_button = QPushButton(self.message_widget)
            example_button.setText(tr("Load Example"))
            example_button.pressed.connect(self.load_example_from_messagebar)
            self.message_widget.layout().addWidget(example_button)
            iface.messageBar().pushWidget(self.message_widget, Qgis.MessageLevel.Info)

    def add_layer_indicators(self):
        self._indicators = [NewModelLayerIndicator(layer) for layer in ModelLayer]

    def update_headloss_formula_menu(self):
        project_settings = ProjectSettings(QgsProject.instance())
        current_hlf = project_settings.get(SettingKey.HEADLOSS_FORMULA, HeadlossFormula.HAZEN_WILLIAMS)
        self.headloss_formula_actions[current_hlf].setChecked(True)

    def set_headloss_formula(self, headloss_formula):
        ProjectSettings().set(SettingKey.HEADLOSS_FORMULA, headloss_formula)

    def update_units_menu(self):
        project_settings = ProjectSettings(QgsProject.instance())
        current_unit = project_settings.get(SettingKey.FLOW_UNITS, FlowUnit.LPS)
        self.units_actions[current_unit].setChecked(True)

    def set_units(self, unit):
        ProjectSettings().set(SettingKey.FLOW_UNITS, unit)

    def update_duration_menu(self):
        project_settings = ProjectSettings(QgsProject.instance())
        current_duration = math.floor(project_settings.get(SettingKey.SIMULATION_DURATION, 0))
        if current_duration not in self.duration_actions:
            self.duration_actions[current_duration] = QAction(
                tr("%n hours", n=current_duration), self.duration_menu, checkable=True
            )
            self.duration_actions[current_duration].setData(current_duration)
            self.duration_actions[current_duration].triggered.connect(
                lambda _, param=current_duration: self.set_duration(param)
            )
            self.duration_menu.addAction(self.duration_actions[current_duration])
            self.duration_group.addAction(self.duration_actions[current_duration])
        self.duration_actions[current_duration].setChecked(True)

    def set_duration(self, duration):
        ProjectSettings().set(SettingKey.SIMULATION_DURATION, duration)

    def load_example_from_messagebar(self):
        self.message_widget.dismiss()
        self.load_example()

    def onClosePlugin(self) -> None:  # noqa N802
        """Cleanup necessary items here when plugin dockwidget is closed"""

    def unload(self) -> None:
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions.values():
            iface.removePluginMenu(self.menu, action)
            iface.removeToolBarIcon(action)

        # if self.examplebutton:
        #    self.examplebutton.disconnect()
        # teardown_logger("wntrqgis")

        # QgsProject.instance().customVariablesChanged.disconnect(self.add_layer_indicators)
        # QgsProject.instance().layerTreeRoot().addedChildren.disconnect(self.add_layer_indicators)

        QgsApplication.processingRegistry().removeProvider(self.provider)
        for indicator in self._indicators:
            indicator.destroy()

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
                    tr("Error"), feedback.errors[0], level=Qgis.MessageLevel.Critical, duration=0
                )

                QgsMessageLog.logMessage(
                    "Task finished unsucessfully\n" + feedback.htmlLog(), MESSAGE_CATEGORY, Qgis.MessageLevel.Warning
                )
                iface.statusBarIface().clearMessage()
                return

            import processing

            processing.gui.Postprocessing.handleAlgorithmResults(algorithm, context, feedback, results)
            iface.statusBarIface().clearMessage()
            if on_finish:
                on_finish()
            if success_message:
                iface.messageBar().pushMessage(
                    tr("Success"),
                    success_message,
                    level=Qgis.MessageLevel.Success,
                    duration=5,
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

        processing.execAlgorithmDialog("wntr:run")

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
        layer = QgsRasterLayer(tms, "Open Street Map", "wms")
        layer.setOpacity(0.5)
        QgsProject.instance().addMapLayer(layer, False)
        root.insertChildNode(len(root.children()), QgsLayerTreeLayer(layer))


class WqProcessingFeedback(QgsProcessingFeedback):
    def __init__(self, logFeedback: bool = True):  # noqa
        self.errors: list[str] = []
        super().__init__(logFeedback)

    def setProgressText(self, text: str | None):  # noqa N802
        iface.statusBarIface().showMessage(text)

        super().setProgressText(text)

    def reportError(self, error: str | None, fatalError: bool = False):  # noqa N802
        if not error:
            return
        self.errors.append(error)


def import_wntr(task: QgsTask):  # noqa: ARG001
    """Pre-import wntr to speed up loading"""
    import wntr  # type: ignore

    if not Path(wntr.__file__).exists():
        msg = "File missing - probably due to plugin upgrade"
        raise ImportError(msg)


def join_pixmap(p1, p2):
    # s = p1.size().expandedTo(p2.size())
    result = QPixmap(128, 128)
    result.fill(QColorConstants.Transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.drawPixmap(0, 0, 128, 128, p1)
    # painter.drawPixmap(result.rect(), p2, p2.rect())
    painter.drawPixmap(64, 64, 64, 64, p2)
    painter.end()
    return result


class NewModelLayerIndicator(QgsLayerTreeViewIndicator):
    layer_id_changed = pyqtSignal()

    def __init__(self, layer_type: ModelLayer):
        super().__init__()
        self.layer_id = None
        self.layer_type = layer_type
        self.setIcon(QIcon(":wntrqgis/logo.svg"))
        self.setToolTip(layer_type.friendly_name)
        self.layer_id_changed.connect(self.search_new_layer)
        self.check_layer_id()
        QgsProject.instance().customVariablesChanged.connect(self.check_layer_id)
        QgsProject.instance().layerTreeRoot().addedChildren.connect(self.search_new_layer)

    def destroy(self):
        self.layer_id = None
        self.layer_id_changed.emit()
        self.deleteLater()

    @pyqtSlot()
    def check_layer_id(self):
        layer_id = ProjectSettings().get(SettingKey.MODEL_LAYERS, {}).get(self.layer_type.name)
        if layer_id != self.layer_id:
            self.layer_id = layer_id
            self.layer_id_changed.emit()

    @pyqtSlot()
    @pyqtSlot(QObject)
    @pyqtSlot(QgsLayerTreeNode, int, int)
    def search_new_layer(self, *_):
        layer = QgsProject.instance().layerTreeRoot().findLayer(self.layer_id)
        if not layer:
            return

        iface.layerTreeView().addIndicator(layer, self)
        layer.destroyed.connect(self.search_new_layer)
        self.layer_id_changed.connect(lambda: self.remove_from_layer(layer))

    @pyqtSlot(QgsLayerTreeLayer)
    def remove_from_layer(self, layer):
        with contextlib.suppress(RuntimeError | TypeError):  # if layer is already deleted
            iface.layerTreeView().removeIndicator(layer, self)
            layer.destroyed.disconnect(self.search_new_layer)
