#===============================================================================
# LICENSE Retrospect-Framework - CC BY-NC-ND
#===============================================================================
# This work is licenced under the Creative Commons
# Attribution-Non-Commercial-No Derivative Works 3.0 Unported License. To view a
# copy of this licence, visit http://creativecommons.org/licenses/by-nc-nd/3.0/
# or send a letter to Creative Commons, 171 Second Street, Suite 300,
# San Francisco, California 94105, USA.
#===============================================================================
import hashlib
import shutil
import os

from textures import TextureHandler


class Cached(TextureHandler):
    # we should keep track of which ones we already used in this session, so we can refetch it in a purge situation.
    __retrievedTexturePaths = []

    def __init__(self, cdnUrl, cachePath, logger, uriHandler):
        TextureHandler.__init__(self, logger, setCdn=True)

        self.__cdnUrl = cdnUrl
        if not self.__cdnUrl:
            self.__cdnUrl = "http://www.rieter.net/net.rieter.xot.cdn/"

        self.__channelTexturePath = os.path.join(cachePath, "textures")
        if not os.path.isdir(self.__channelTexturePath):
            os.makedirs(self.__channelTexturePath)

        self.__uriHandler = uriHandler

        self.__textureQueue = {}

    def GetTextureUri(self, channel, fileName):
        """ Gets the full URI for the image file. Depending on the type of textures handling, it might also cache
        the texture and return that path.

        @param fileName: the file name
        @param channel:  the channel

        @return: the texture path

        """

        if fileName is None or fileName == "":
            return fileName

        if fileName.startswith("http"):
            self._logger.Trace("Not going to resolve http(s) texture: '%s'.", fileName)
            return fileName

        if os.path.isabs(fileName):
            self._logger.Trace("Already cached texture found: '%s'", fileName)
            return fileName

        # Check if we already have the file
        cdnFolder = self._GetCdnSubFolder(channel)
        textureDir = os.path.join(self.__channelTexturePath, cdnFolder)
        if not os.path.isdir(textureDir):
            os.makedirs(textureDir)

        texturePath = os.path.join(self.__channelTexturePath, cdnFolder, fileName)

        if not os.path.isfile(texturePath):
            # Missing item. Fetch it
            localPath = os.path.join(channel.path, fileName)
            if os.path.isfile(localPath):
                self._logger.Debug("Fetching texture '%s' from '%s'", fileName, localPath)
                shutil.copyfile(localPath, texturePath)
            else:
                uri = "%s/%s/%s" % (self.__cdnUrl, cdnFolder, fileName)
                self._logger.Debug("Queueing texture '%s' for caching from '%s'", fileName, uri)
                self.__textureQueue[uri] = texturePath

                self.__FetchTexture(uri, texturePath)

        self._logger.Trace("Returning cached texture for '%s' from '%s'", fileName, texturePath)
        Cached.__retrievedTexturePaths.append(texturePath)
        return texturePath

    def FetchTextures(self):
        """ Fetches all the needed textures """
        pass

    def PurgeTextureCache(self, channel):
        """ Removes those entries from the textures cache that are no longer required.

        @param channel:  the channel

        """

        self._logger.Info("Purging Texture for: %s", channel.path)

        # read the md5 hashes
        addonId = self._GetAddonId(channel)
        fp = file(os.path.join(channel.path, "..", "%s.md5" % (addonId, )))
        lines = fp.readlines()
        fp.close()

        # get a lookup table
        textures = [reversed(line.rstrip().split(" ", 1)) for line in lines]
        # noinspection PyTypeChecker
        textures = dict(textures)

        # remove items not in the textures.md5
        cdnFolder = self._GetCdnSubFolder(channel)
        texturePath = os.path.join(self.__channelTexturePath, cdnFolder)
        if not os.path.isdir(texturePath):
            self._logger.Warning("Missing path '%s' to purge", texturePath)
            return

        images = [image for image in os.listdir(texturePath)
                  if image.lower().endswith(".png") or image.lower().endswith(".jpg")]

        textureChange = False

        for image in images:
            imageKey = "%s/%s" % (cdnFolder, image)
            filePath = os.path.join(self.__channelTexturePath, cdnFolder, image)

            if imageKey in textures:
                # verify the MD5 in the textures.md5
                md5 = self.__GetHash(filePath)
                if md5 == textures[imageKey]:
                    self._logger.Trace("Texture up to date: %s", filePath)
                else:
                    self._logger.Warning("Texture expired: %s", filePath)
                    os.remove(filePath)
                    textureChange = True

                    # and fetch the updated one if it was already used
                    if filePath in Cached.__retrievedTexturePaths:
                        self.GetTextureUri(channel, image)
            else:
                self._logger.Warning("Texture no longer required: %s", filePath)
                os.remove(filePath)
                textureChange = True

        # always reset the Kodi Texture cache for this channel
        if textureChange:
            self._PurgeXbmcCache(cdnFolder)

        return

    def __FetchTexture(self, uri, texturePath):
        """ Fetches a texture

        @param uri:         string - The uri to fetch from
        @param texturePath: string - The path to store to

        """

        imageBytes = self.__uriHandler.Open(uri)
        if imageBytes:
            fs = open(texturePath, mode='wb')
            fs.write(imageBytes)
            fs.close()
            TextureHandler._bytesTransfered += len(imageBytes)
            self._logger.Debug("Retrieved texture: %s", uri)
        else:
            # fallback to local cache.
            # texturePath = os.path.join(self._channelPath, fileName)
            # self._logger.Error("Could not update Texture: %s. Falling back to: %s", uri, texturePath)
            self._logger.Error("Could not update Texture:\nSource: '%s'\nTarget: '%s'", uri, texturePath)
        return

    def __GetHash(self, filePath):
        """ Returns the hash for the given file

        @param filePath: string - The file to generate a hash from

        @return: MD5 has for the file

        """

        hashObject = hashlib.md5()
        with open(filePath, "rb") as fs:
            for block in iter(lambda: fs.read(65536), ""):
                hashObject.update(block)
        md5 = hashObject.hexdigest()
        return md5
