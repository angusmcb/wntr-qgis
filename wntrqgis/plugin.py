from __future__ import annotations

from typing import Callable

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsLayerTreeLayer,
    QgsMessageLog,
    QgsProcessingAlgRunnerTask,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingOutputLayerDefinition,
    QgsProject,
    QgsRasterLayer,
)
from qgis.gui import QgsProjectionSelectionDialog

# from qgis.processing import execAlgorithmDialog for qgis 3.40 onwarrds
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QWidget
from qgis.utils import iface

from wntrqgis.expressions.wntr_result_at_current_time import wntr_result_at_current_time  # noqa F401
from wntrqgis.network_parts import (
    WqFlowUnit,
    WqHeadlossFormula,
    WqModelLayer,
    WqProjectSetting,
    WqProjectSettings,
    WqResultLayer,
)
from wntrqgis.resource_manager import WqExampleInp, WqIcon, join_pixmap
from wntrqgis.wntrqgis_processing.provider import Provider

MESSAGE_CATEGORY = "WNTR-QGIS"


class Plugin:
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

        self.actions: list[QAction] = []
        self.menu = "Water Network Tools for Resilience"

    def add_action(
        self,
        icon_path: str,
        text: str,
        callback: Callable,
        *,
        enabled_flag: bool = True,
        add_to_menu: bool = True,
        add_to_toolbar: bool = True,
        status_tip: str | None = None,
        whats_this: str | None = None,
        parent: QWidget | None = None,
    ) -> QAction:
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

        self.actions.append(action)

        return action

    def initProcessing(self):  # noqa N802
        self.provider = Provider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self) -> None:  # noqa N802
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        # self._progress_bar = QProgressBar()
        # self._progress_bar.setRange(0, 0)
        # # iface.mainWindow().statusBar().addWidget(progress_bar)
        # # Could be replaced by the following if you want same position as the default QGIS component for progress bar

        # self._progress_bar.hide()
        # iface.statusBarIface().addPermanentWidget(self._progress_bar)

        self.add_action(
            join_pixmap(WqIcon.NEW.q_pixmap, WqIcon.LOGO.q_pixmap),
            text="Create Template Layers",
            callback=self.create_template_layers,
            parent=iface.mainWindow(),
            add_to_toolbar=True,
        )
        self.add_action(
            join_pixmap(WqIcon.OPEN.q_pixmap, WqIcon.LOGO.q_pixmap),
            text="Load from .inp file",
            callback=self.load_inp_file,
            parent=iface.mainWindow(),
            add_to_toolbar=True,
        )
        self.add_action(
            join_pixmap(WqIcon.RUN.q_pixmap, WqIcon.LOGO.q_pixmap),
            text="Run Simulation",
            callback=self.run_simulation,
            parent=iface.mainWindow(),
            add_to_toolbar=True,
        )
        self.add_action(
            join_pixmap(QPixmap(":images/themes/default/propertyicons/settings.svg"), WqIcon.LOGO.q_pixmap),
            text="Settings",
            callback=self.open_settings,
            parent=iface.mainWindow(),
            add_to_toolbar=True,
        )
        self.add_action(
            "", text="Load Example", callback=self.load_example, parent=iface.mainWindow(), add_to_toolbar=False
        )

        self.initProcessing()

    def onClosePlugin(self) -> None:  # noqa N802
        """Cleanup necessary items here when plugin dockwidget is closed"""

    def unload(self) -> None:
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            iface.removePluginMenu(self.menu, action)
            iface.removeToolBarIcon(action)
        # teardown_logger("wntrqgis")
        QgsApplication.processingRegistry().removeProvider(self.provider)

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
                iface.messageBar().pushMessage("Error", feedback.errors[0], level=Qgis.Critical, duration=5)
                QgsMessageLog.logMessage(
                    "Task finished unsucessfully\n" + feedback.htmlLog(), MESSAGE_CATEGORY, Qgis.Warning
                )
                iface.statusBarIface().clearMessage()
                return

            # this import is here to not break pytest
            from processing.gui.Postprocessing import handleAlgorithmResults

            handleAlgorithmResults(algorithm, context, feedback, results)
            iface.statusBarIface().clearMessage()
            if on_finish:
                on_finish()
            if success_message:
                iface.messageBar().pushMessage(
                    "Success",
                    success_message,
                    level=Qgis.Success,
                    duration=5,
                )

        task = QgsProcessingAlgRunnerTask(algorithm, parameters, context, feedback)
        task.executed.connect(task_finished)
        QgsApplication.taskManager().addTask(task)

    def create_template_layers(self) -> None:
        parameters = {"CRS": QgsProject.instance().crs(), **self._empty_model_layer_dict()}
        self.run_alg_async("wntr:templatelayers", parameters, success_message="Template Layers Created")

    def load_inp_file(self) -> None:
        filepath, _ = QFileDialog.getOpenFileName(
            None, "Choose Input File", QSettings().value("UI/lastProjectDir"), "EPANET INP File (*.inp)"
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
            success_message="Loaded .inp file",
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

        inp_file = str(WqExampleInp.KY10.path)
        parameters = {"INPUT": inp_file, "CRS": network_crs, **self._empty_model_layer_dict()}
        self.run_alg_async(
            "wntr:importinp",
            parameters,
            on_finish=self.load_osm,
            success_message="Example loaded with Open Street Map background",
        )

    def open_settings(self) -> None:
        from processing import execAlgorithmDialog

        execAlgorithmDialog("wntr:settings")

    def run_simulation(self) -> None:
        project_settings = WqProjectSettings(QgsProject.instance())
        saved_layers = project_settings.get(WqProjectSetting.MODEL_LAYERS, {})
        input_layers = {layer_type.name: saved_layers.get(layer_type.name) for layer_type in WqModelLayer}
        result_layers = {layer.value: self._temporary_processing_output() for layer in WqResultLayer}
        flow_units = project_settings.get(WqProjectSetting.FLOW_UNITS, WqFlowUnit.LPS)
        flow_unit_id = list(WqFlowUnit).index(flow_units)
        headloss_formula = project_settings.get(WqProjectSetting.HEADLOSS_FORMULA, WqHeadlossFormula.HAZEN_WILLIAMS)
        headloss_formula_id = list(WqHeadlossFormula).index(headloss_formula)
        duration = project_settings.get(WqProjectSetting.SIMULATION_DURATION, 0)
        parameters = {
            "UNITS": flow_unit_id,
            "HEADLOSS_FORMULA": headloss_formula_id,
            "DURATION": duration,
            **result_layers,
            **input_layers,
        }

        success_message = (
            f"Analysed using units '{flow_units.value}' and headloss formula '{headloss_formula.friendly_name}'"
        )

        self.run_alg_async(
            "wntr:run",
            parameters,
            success_message=success_message,
        )

    def _temporary_processing_output(self):
        return QgsProcessingOutputLayerDefinition("TEMPORARY_OUTPUT", QgsProject.instance())

    def _empty_model_layer_dict(self):
        return {layer.value: self._temporary_processing_output() for layer in WqModelLayer}

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
