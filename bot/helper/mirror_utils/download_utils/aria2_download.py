import threading

from time import sleep

from bot import aria2, download_dict_lock, download_dict, STOP_DUPLICATE, TORRENT_DIRECT_LIMIT, ZIP_UNZIP_LIMIT, LOGGER
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.ext_utils.bot_utils import is_magnet, getDownloadByGid, new_thread, get_readable_file_size
from bot.helper.telegram_helper.message_utils import *
from .download_helper import DownloadHelper
from bot.helper.mirror_utils.status_utils.aria_download_status import AriaDownloadStatus
from bot.helper.telegram_helper.message_utils import sendMarkup, sendStatusMessage, sendMessage
from aria2p import API


def add_aria2c_download(link: str, path, listener, filename):
        if is_magnet(link):
            download = aria2.add_magnet(link, {'dir': path, 'out': filename})
        else:
            download = aria2.add_uris([link], {'dir': path, 'out': filename})
        if download.error_message:
            error = str(download.error_message).replace('<', ' ').replace('>', ' ')
            LOGGER.info(f"Download Error: {error}")
            return sendMessage(error, listener.bot, listener.update)
        with download_dict_lock:
            download_dict[listener.uid] = AriaDownloadStatus(download.gid, listener)
            LOGGER.info(f"Started: {download.gid} DIR: {download.dir} ")
        sendStatusMessage(listener.update, listener.bot)



class AriaDownloadHelper(DownloadHelper):

    def __init__(self):
        super().__init__()

    @new_thread
    def __onDownloadStarted(self, api, gid):
        if STOP_DUPLICATE or TORRENT_DIRECT_LIMIT is not None or ZIP_UNZIP_LIMIT is not None:
            sleep(2)
            dl = getDownloadByGid(gid)
            download = aria2.get_download(gid)
            if STOP_DUPLICATE and dl is not None:
                LOGGER.info(f"Checking File/Folder if already in Drive...")
                sname = aria2.get_download(gid).name
                if dl.getListener().isZip:
                    sname = sname + ".zip"
                if dl.getListener().extract:
                    smsg = None
                else:
                    gdrive = GoogleDriveHelper(None)
                    smsg, button = gdrive.drive_list(sname)
                if smsg:
                    dl.getListener().onDownloadError(f'File/Folder already available in Drive.\n\n')
                    aria2.remove([download], force=True)
                    sendMarkup("Here are the search results:", dl.getListener().bot, dl.getListener().update, button)
                    return
            if dl is not None and (ZIP_UNZIP_LIMIT is not None or TORRENT_DIRECT_LIMIT is not None):
                limit = None
                if ZIP_UNZIP_LIMIT is not None and (dl.getListener().isTar or dl.getListener().extract):
                    LOGGER.info(f"Checking File/Folder Size...")
                    limit = ZIP_UNZIP_LIMIT
                    mssg = f'Zip/Unzip limit is {ZIP_UNZIP_LIMIT}GB'
                elif TORRENT_DIRECT_LIMIT is not None and limit is None:
                    LOGGER.info(f"Checking File/Folder Size...")
                    limit = TORRENT_DIRECT_LIMIT
                    mssg = f'Torrent/Direct limit is {TORRENT_DIRECT_LIMIT}'
                if limit is not None:
                    size = aria2.get_download(gid).total_length
                    limit = limit.split(' ', maxsplit=1)
                    limitint = int(limit[0])
                    if 'G' in limit[1] or 'g' in limit[1]:
                        if size > limitint * 1024**3:
                            dl.getListener().onDownloadError(f'{mssg}.\nYour File/Folder size is {get_readable_file_size(size)}')
                            aria2.remove([download], force=True)
                            return
                    elif 'T' in limit[1] or 't' in limit[1]:
                        if size > limitint * 1024**4:
                            dl.getListener().onDownloadError(f'{mssg}.\nYour File/Folder size is {get_readable_file_size(size)}')
                            aria2.remove([download], force=True)
                            return
        update_all_messages()

    def __onDownloadComplete(self, api: API, gid):
        dl = getDownloadByGid(gid)
        download = aria2.get_download(gid)
        if download.followed_by_ids:
            new_gid = download.followed_by_ids[0]
            new_download = aria2.get_download(new_gid)
            if dl is None:
                dl = getDownloadByGid(new_gid)
            with download_dict_lock:
                download_dict[dl.uid()] = AriaDownloadStatus(new_gid, dl.getListener())
                if new_download.is_torrent:
                    download_dict[dl.uid()].is_torrent = True
            update_all_messages()
            LOGGER.info(f'Changed gid from {gid} to {new_gid}')
        else:
            if dl:
                threading.Thread(target=dl.getListener().onDownloadComplete).start()

    @new_thread
    def __onDownloadStopped(self, api, gid):
        sleep(4)
        dl = getDownloadByGid(gid)
        if dl: 
            dl.getListener().onDownloadError('Dead torrent!')

    @new_thread
    def __onDownloadError(self, api, gid):
        LOGGER.info(f"onDownloadError: {gid}")
        sleep(0.5)  # sleep for split second to ensure proper dl gid update from onDownloadComplete
        dl = getDownloadByGid(gid)
        download = aria2.get_download(gid)
        error = download.error_message
        LOGGER.info(f"Download Error: {error}")
        if dl: 
            dl.getListener().onDownloadError(error)

    def start_listener(self):
        aria2.listen_to_notifications(threaded=True, on_download_start=self.__onDownloadStarted,
                                      on_download_error=self.__onDownloadError,
                                      on_download_stop=self.__onDownloadStopped,
                                      on_download_complete=self.__onDownloadComplete,
                                      timeout=1)

    def add_download(self, link: str, path, listener, filename):
        if is_magnet(link):
            download = aria2.add_magnet(link, {'dir': path, 'out': filename})
        else:
            download = aria2.add_uris([link], {'dir': path, 'out': filename})
        if download.error_message:  # no need to proceed further at this point
            listener.onDownloadError(download.error_message)
            return
        with download_dict_lock:
            download_dict[listener.uid] = AriaDownloadStatus(download.gid, listener)
            LOGGER.info(f"Started: {download.gid} DIR:{download.dir} ")
            
    def add_aria2c_download(link: str, path, listener, filename):
        if is_magnet(link):
            download = aria2.add_magnet(link, {'dir': path, 'out': filename})
        else:
            download = aria2.add_uris([link], {'dir': path, 'out': filename})
        if download.error_message:
            error = str(download.error_message).replace('<', ' ').replace('>', ' ')
            LOGGER.info(f"Download Error: {error}")
            return sendMessage(error, listener.bot, listener.update)
        with download_dict_lock:
            download_dict[listener.uid] = AriaDownloadStatus(download.gid, listener)
            LOGGER.info(f"Started: {download.gid} DIR: {download.dir} ")
        sendStatusMessage(listener.update, listener.bot)
    