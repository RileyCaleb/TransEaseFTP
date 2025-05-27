import os
import sys
import logging
import configparser
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QTextEdit, QGroupBox, QMessageBox,
                             QFileDialog, QStatusBar, QLineEdit, QSystemTrayIcon, QMenu,
                             QAction, QStyle, QTabWidget, QComboBox, QSpinBox, QCheckBox)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QTextCursor, QFont, QIcon, QPixmap
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from typing import Dict, Any, Optional


class FTPSignals(QObject):
    """集中管理FTP服务器信号"""
    log_received = pyqtSignal(str)
    status_update = pyqtSignal(str)
    connection_update = pyqtSignal(int)
    server_started = pyqtSignal()
    server_stopped = pyqtSignal()
    error_occurred = pyqtSignal(str)


class FTPConfigManager:
    """带有验证的增强型配置管理"""
    DEFAULT_CONFIG = {
        'general': {
            'port': '21',
            'root_path': os.path.abspath(os.getcwd()),
            'max_connections': '50',
            'timeout': '300',
            'encoding': 'gb18030',
            'log_level': 'INFO',
            'save_log': 'False'
        }
    }

    def __init__(self, config_path='config.ini'):
        self.config_path = os.path.abspath(config_path)
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self) -> None:
        """加载或创建配置文件"""
        if not os.path.exists(self.config_path):
            self.create_default_config()

        self.config.read(self.config_path, encoding='utf-8')

        # 确保所有配置项都存在
        for section, options in self.DEFAULT_CONFIG.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
            for key, value in options.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, value)

        # 验证并创建根目录
        root_path = self.get('general', 'root_path')
        try:
            os.makedirs(root_path, exist_ok=True)
        except Exception as e:
            logging.error(f"无法创建根目录 '{root_path}': {e}")
            # 回退到默认目录
            default_path = os.path.abspath(os.getcwd())
            self.config.set('general', 'root_path', default_path)
            os.makedirs(default_path, exist_ok=True)

    def create_default_config(self) -> None:
        """创建默认配置文件"""
        for section, options in self.DEFAULT_CONFIG.items():
            self.config.add_section(section)
            for key, value in options.items():
                self.config.set(section, key, value)

        with open(self.config_path, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def get(self, section: str, key: str) -> Any:
        """获取配置值并进行类型转换"""
        try:
            if section == 'general':
                if key == 'port':
                    return self.config.getint(section, key)
                elif key in ['max_connections', 'timeout']:
                    return self.config.getint(section, key)
                elif key == 'save_log':
                    return self.config.getboolean(section, key)
            return self.config.get(section, key)
        except (configparser.NoOptionError, configparser.NoSectionError, ValueError):
            return self.DEFAULT_CONFIG.get(section, {}).get(key)

    def save(self, settings: Dict[str, Dict[str, Any]]) -> bool:
        """保存配置并进行验证"""
        try:
            for section, options in settings.items():
                for key, value in options.items():
                    # 特殊处理路径配置，确保存储绝对路径
                    if key == 'root_path':
                        value = os.path.abspath(str(value))
                    self.config.set(section, key, str(value))

            # 验证端口范围
            port = self.config.getint('general', 'port')
            if not 1 <= port <= 65535:
                raise ValueError("端口必须在1-65535范围内")

            # 验证根目录
            root_path = self.config.get('general', 'root_path')
            if not os.path.isdir(root_path):
                os.makedirs(root_path, exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                self.config.write(f)

            return True
        except Exception as e:
            logging.error(f"保存配置失败: {e}")
            return False


class FTPServerThread(QThread):
    """线程安全的FTP服务器实现"""
    def __init__(self, handler: FTPHandler, host: str, port: int, max_connections: int):
        super().__init__()
        self.handler = handler
        self.host = host
        self.port = port
        self.max_connections = max_connections
        self.server = None
        self._running = False

    def run(self) -> None:
        """启动FTP服务器"""
        try:
            self.server = FTPServer((self.host, self.port), self.handler)
            self.server.max_cons = self.max_connections
            self._running = True
            self.server.serve_forever()
        except Exception as e:
            logging.error(f"服务器错误: {e}")
        finally:
            self._running = False

    def stop(self) -> None:
        """优雅地停止FTP服务器"""
        if self.server and self._running:
            try:
                self.server.close_all()
            except Exception as e:
                logging.error(f"关闭服务器时出错: {e}")
            self._running = False


class WindowsFTPHandler(FTPHandler):
    """支持GB18030编码的Windows优化FTP处理器"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.encoding = 'gb18030'
        self.utf8 = False
        self.banner = "220 FTP服务器已就绪。"
        self.permit_privileged_ports = True
        self.permit_foreign_addresses = True
        self.unicode_errors = 'replace'

    def decode(self, bytes):
        """重写解码方法以支持GB18030"""
        try:
            return bytes.decode(self.encoding, errors=self.unicode_errors)
        except UnicodeDecodeError:
            return bytes.decode('latin1', errors=self.unicode_errors)

    def encode(self, string):
        """重写编码方法以支持GB18030"""
        try:
            return string.encode(self.encoding, errors=self.unicode_errors)
        except UnicodeEncodeError:
            return string.encode('latin1', errors=self.unicode_errors)


class FTPLogger(logging.Handler):
    """用于GUI集成的自定义日志处理器"""
    def __init__(self, signals: FTPSignals):
        super().__init__()
        self.signals = signals
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    def emit(self, record) -> None:
        """发送日志记录到GUI"""
        log_entry = self.format(record)
        self.signals.log_received.emit(log_entry)


class FTPMainWindow(QMainWindow):
    """具有完整功能的主应用程序窗口"""
    def __init__(self, config_path='config.ini'):
        super().__init__()
        self.setWindowTitle("FTP服务器管理工具(优化版)")
        self.resize(900, 700)

        # 初始化组件
        self.config = FTPConfigManager(config_path)
        self.signals = FTPSignals()
        self.server_thread = None

        # 设置UI和连接
        self._setup_ui()
        self._setup_logging()
        self._setup_connections()
        self._setup_tray_icon()

        # 初始UI状态
        self._update_ui_state(False)

    def _setup_ui(self) -> None:
        """初始化用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 创建标签页界面
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # 服务器控制标签页
        self._setup_server_tab(tab_widget)
        # 配置标签页
        self._setup_config_tab(tab_widget)
        # 日志标签页
        self._setup_log_tab(tab_widget)

        # 带有连接计数器的状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

        self.connections_label = QLabel("连接数: 0")
        self.status_bar.addPermanentWidget(self.connections_label)

    def _setup_server_tab(self, tab_widget: QTabWidget) -> None:
        """设置服务器控制标签页"""
        server_tab = QWidget()
        layout = QVBoxLayout(server_tab)

        # 服务器信息组
        info_group = QGroupBox("服务器信息")
        info_layout = QVBoxLayout(info_group)

        self.server_status = QLabel("状态: 已停止")
        self.server_address = QLabel(f"地址: 0.0.0.0:{self.config.get('general', 'port')}")
        self.server_root = QLabel(f"根目录: {self.config.get('general', 'root_path')}")

        info_layout.addWidget(self.server_status)
        info_layout.addWidget(self.server_address)
        info_layout.addWidget(self.server_root)

        # 控制按钮组
        control_group = QGroupBox("控制")
        control_layout = QHBoxLayout(control_group)

        self.start_btn = QPushButton("启动")
        self.start_btn.clicked.connect(self._toggle_server)

        select_dir_btn = QPushButton("选择根目录")
        select_dir_btn.clicked.connect(self._select_root_dir)

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(select_dir_btn)

        layout.addWidget(info_group)
        layout.addWidget(control_group)
        layout.addStretch()

        tab_widget.addTab(server_tab, "服务器")

    def _setup_config_tab(self, tab_widget: QTabWidget) -> None:
        """设置配置标签页"""
        config_tab = QWidget()
        layout = QVBoxLayout(config_tab)

        form_group = QGroupBox("基本配置")
        form_layout = QVBoxLayout(form_group)

        # 端口设置
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("端口:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(self.config.get('general', 'port'))
        port_layout.addWidget(self.port_spin)
        form_layout.addLayout(port_layout)

        # 最大连接数
        max_conn_layout = QHBoxLayout()
        max_conn_layout.addWidget(QLabel("最大连接数:"))
        self.max_conn_spin = QSpinBox()
        self.max_conn_spin.setRange(1, 1000)
        self.max_conn_spin.setValue(self.config.get('general', 'max_connections'))
        max_conn_layout.addWidget(self.max_conn_spin)
        form_layout.addLayout(max_conn_layout)

        # 超时设置
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("超时(秒):"))
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 3600)
        self.timeout_spin.setValue(self.config.get('general', 'timeout'))
        timeout_layout.addWidget(self.timeout_spin)
        form_layout.addLayout(timeout_layout)

        # 编码设置
        encoding_layout = QHBoxLayout()
        encoding_layout.addWidget(QLabel("编码:"))
        self.encoding_combo = QComboBox()
        self.encoding_combo.addItems(['gb18030', 'utf-8', 'latin1'])
        self.encoding_combo.setCurrentText(self.config.get('general', 'encoding'))
        encoding_layout.addWidget(self.encoding_combo)
        form_layout.addLayout(encoding_layout)

        # 日志级别设置
        log_level_layout = QHBoxLayout()
        log_level_layout.addWidget(QLabel("日志级别:"))
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        self.log_level_combo.setCurrentText(self.config.get('general', 'log_level'))
        log_level_layout.addWidget(self.log_level_combo)
        form_layout.addLayout(log_level_layout)

        # 日志保存设置
        self.save_log_check = QCheckBox("保存日志到文件")
        self.save_log_check.setChecked(self.config.get('general', 'save_log'))
        form_layout.addWidget(self.save_log_check)

        # 保存按钮
        save_btn = QPushButton("保存配置")
        save_btn.clicked.connect(self._save_settings)
        form_layout.addWidget(save_btn)

        layout.addWidget(form_group)
        layout.addStretch()

        tab_widget.addTab(config_tab, "配置")

    def _setup_log_tab(self, tab_widget: QTabWidget) -> None:
        """设置日志标签页"""
        log_tab = QWidget()
        layout = QVBoxLayout(log_tab)

        log_group = QGroupBox("服务器日志")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))

        # 日志控制
        log_control_layout = QHBoxLayout()
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(lambda: self.log_text.clear())

        log_control_layout.addWidget(self.clear_log_btn)
        log_control_layout.addStretch()

        log_layout.addLayout(log_control_layout)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

        tab_widget.addTab(log_tab, "日志")

    def _setup_logging(self) -> None:
        """配置日志系统"""
        logger = logging.getLogger()
        logger.handlers.clear()
        logger.setLevel(self.config.get('general', 'log_level'))

        # GUI日志处理器
        gui_handler = FTPLogger(self.signals)
        logger.addHandler(gui_handler)

        # 如果启用则添加文件日志处理器
        if self.config.get('general', 'save_log'):
            log_file = os.path.join(os.path.dirname(self.config.config_path), 'ftp_server.log')
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(file_handler)

    def _setup_connections(self) -> None:
        """连接所有信号和槽"""
        self.signals.log_received.connect(self._append_log)
        self.signals.status_update.connect(self.status_bar.showMessage)
        self.signals.connection_update.connect(self._update_connections)
        self.signals.server_started.connect(lambda: self._update_ui_state(True))
        self.signals.server_stopped.connect(lambda: self._update_ui_state(False))
        self.signals.error_occurred.connect(self._show_error)

    def _setup_tray_icon(self) -> None:
        """配置系统托盘图标"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))

        # 创建托盘菜单
        tray_menu = QMenu()

        self.toggle_action = tray_menu.addAction("启动服务器")
        self.toggle_action.triggered.connect(self._toggle_server)

        tray_menu.addSeparator()

        show_action = tray_menu.addAction("显示窗口")
        show_action.triggered.connect(self.show_normal)

        hide_action = tray_menu.addAction("隐藏窗口")
        hide_action.triggered.connect(self.hide)

        tray_menu.addSeparator()

        exit_action = tray_menu.addAction("退出")
        exit_action.triggered.connect(self.close_application)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_icon_activated)
        self.tray_icon.show()

        self._update_tray_menu()

    def _update_ui_state(self, running: bool) -> None:
        """根据服务器状态更新UI元素"""
        self.start_btn.setText("停止" if running else "启动")
        self.server_status.setText(f"状态: {'运行中' if running else '已停止'}")
        self._update_tray_menu()

    def _update_tray_menu(self) -> None:
        """根据服务器状态更新托盘菜单"""
        running = self.server_thread is not None and self.server_thread.isRunning()
        self.toggle_action.setText("停止服务器" if running else "启动服务器")
        self.tray_icon.setToolTip(f"FTP服务器 {'运行中' if running else '已停止'}")

    def _update_connections(self, count: int) -> None:
        """更新连接计数器"""
        self.connections_label.setText(f"连接数: {count}")

    def _toggle_server(self) -> None:
        """切换服务器状态(启动/停止)"""
        if self.server_thread and self.server_thread.isRunning():
            self._stop_server()
        else:
            self._start_server()

    def _start_server(self) -> None:
        """启动FTP服务器"""
        try:
            # 创建授权器并添加匿名用户
            authorizer = DummyAuthorizer()
            root_path = self.config.get('general', 'root_path')
            authorizer.add_anonymous(root_path, perm='elradfmwM')

            # 使用当前设置创建处理器
            handler = WindowsFTPHandler
            handler.authorizer = authorizer
            handler.timeout = self.config.get('general', 'timeout')
            handler.encoding = self.config.get('general', 'encoding')
            handler.utf8 = self.config.get('general', 'encoding').lower() == 'utf-8'

            # 创建并启动服务器线程
            self.server_thread = FTPServerThread(
                handler=handler,
                host="0.0.0.0",
                port=self.config.get('general', 'port'),
                max_connections=self.config.get('general', 'max_connections')
            )
            self.server_thread.start()

            # 更新UI并通知用户
            self.signals.server_started.emit()
            self.signals.status_update.emit(f"服务器已在端口 {self.config.get('general', 'port')} 启动")
            self.tray_icon.showMessage(
                "FTP服务器",
                f"服务器已在端口 {self.config.get('general', 'port')} 启动",
                QSystemTrayIcon.Information,
                3000
            )

            logging.info(f"服务器已在端口 {self.config.get('general', 'port')} 启动")

        except Exception as e:
            logging.error(f"启动服务器失败: {e}")
            self.signals.error_occurred.emit(f"启动服务器失败: {e}")
            self._update_ui_state(False)

    def _stop_server(self) -> None:
        """停止FTP服务器"""
        if self.server_thread:
            try:
                self.server_thread.stop()
                self.server_thread.quit()
                self.server_thread.wait(2000)

                self.signals.server_stopped.emit()
                self.signals.status_update.emit("服务器已停止")
                self.tray_icon.showMessage(
                    "FTP服务器",
                    "服务器已停止",
                    QSystemTrayIcon.Information,
                    3000
                )

                logging.info("服务器已停止")

            except Exception as e:
                logging.error(f"停止服务器时出错: {e}")
                self.signals.error_occurred.emit(f"停止服务器时出错: {e}")

    def _select_root_dir(self) -> None:
        """选择新的根目录"""
        current_path = self.config.get('general', 'root_path')
        path = QFileDialog.getExistingDirectory(
            self,
            "选择根目录",
            current_path if os.path.exists(current_path) else os.getcwd()
        )

        if path:
            abs_path = os.path.abspath(path)
            if not os.path.exists(abs_path):
                try:
                    os.makedirs(abs_path)
                except Exception as e:
                    self._show_error(f"无法创建目录: {e}")
                    return

            if self.config.save({'general': {'root_path': abs_path}}):
                self.server_root.setText(f"根目录: {abs_path}")
                if self.server_thread and self.server_thread.isRunning():
                    QMessageBox.warning(
                        self,
                        "注意",
                        "必须重启服务器才能使更改生效"
                    )

    def _save_settings(self) -> None:
        """保存当前设置到配置"""
        try:
            settings = {
                'general': {
                    'port': self.port_spin.value(),
                    'max_connections': self.max_conn_spin.value(),
                    'timeout': self.timeout_spin.value(),
                    'encoding': self.encoding_combo.currentText(),
                    'log_level': self.log_level_combo.currentText(),
                    'save_log': self.save_log_check.isChecked()
                }
            }

            if self.config.save(settings):
                # 使用新设置重新配置日志
                self._setup_logging()

                QMessageBox.information(self, "成功", "配置保存成功!")
                if self.server_thread and self.server_thread.isRunning():
                    QMessageBox.warning(
                        self,
                        "注意",
                        "必须重启服务器才能使更改生效"
                    )

        except Exception as e:
            logging.error(f"保存设置失败: {e}")
            self._show_error(f"保存设置失败: {e}")

    def _append_log(self, message: str) -> None:
        """添加消息到日志显示"""
        cursor = self.log_text.textCursor()
        at_bottom = cursor.atEnd()

        self.log_text.moveCursor(QTextCursor.End)
        self.log_text.insertPlainText(message + "\n")

        if at_bottom:
            self.log_text.moveCursor(QTextCursor.End)
        else:
            cursor.setPosition(self.log_text.textCursor().position())
            self.log_text.setTextCursor(cursor)

        # 限制日志大小
        if self.log_text.document().lineCount() > 500:
            self.log_text.setPlainText(
                '\n'.join(self.log_text.toPlainText().split('\n')[-300:])
            )

    def _show_error(self, message: str) -> None:
        """显示错误消息对话框"""
        QMessageBox.critical(self, "错误", message)

    def _on_tray_icon_activated(self, reason) -> None:
        """处理托盘图标激活"""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show_normal()

    def show_normal(self) -> None:
        """以正常状态显示窗口"""
        self.show()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.activateWindow()

    def close_application(self) -> None:
        """干净地退出应用程序"""
        if self.server_thread and self.server_thread.isRunning():
            reply = QMessageBox.question(
                self, '退出',
                "服务器仍在运行。确定要退出吗?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        self.tray_icon.hide()
        if self.server_thread:
            self._stop_server()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        """处理窗口关闭事件"""
        if self.server_thread and self.server_thread.isRunning() and not self.isHidden():
            reply = QMessageBox.question(
                self, '退出',
                "服务器仍在运行。确定要退出吗?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                self._stop_server()
                event.accept()
            else:
                event.ignore()
        elif not self.isHidden():
            self.hide()
            event.ignore()
        else:
            event.accept()


if __name__ == "__main__":
    try:
        # 配置应用程序
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        app.setQuitOnLastWindowClosed(False)

        # 设置应用程序元数据
        app.setApplicationName("FTP服务器管理工具")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("我的公司")

        # 创建并显示主窗口
        window = FTPMainWindow()
        window.show()

        sys.exit(app.exec_())
    except Exception as e:
        logging.exception("应用程序崩溃: ")
        QMessageBox.critical(None, "致命错误", f"未处理的异常: {str(e)}")